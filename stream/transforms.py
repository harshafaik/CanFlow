from datetime import datetime

def flatten_telemetry(data):
    """Flatten nested 'obd' and 'gps' sub-objects into the top-level dictionary."""
    flattened = data.copy()
    obd = flattened.pop('obd', {})
    gps = flattened.pop('gps', {})
    
    flattened.update(obd)
    flattened.update(gps)
    return flattened

def parse_telemetry_types(data):
    """Coerce types for ClickHouse compatibility: ISO strings to datetime objects, others to float."""
    parsed = data.copy()
    
    # Parse timestamp
    if 'timestamp' in parsed and isinstance(parsed['timestamp'], str):
        # DateTime64 in ClickHouse usually expects a datetime object or a specific string format
        try:
            parsed['timestamp'] = datetime.fromisoformat(parsed['timestamp'].replace('Z', '+00:00'))
        except ValueError:
            pass

    # Ensure numeric fields are floats
    numeric_fields = [
        'rpm', 'speed', 'throttle_position', 'coolant_temp', 
        'battery_voltage', 'maf', 'fuel_level', 'latitude', 'longitude'
    ]
    for field in numeric_fields:
        if field in parsed and parsed[field] is not None:
            parsed[field] = float(parsed[field])
            
    return parsed

def detect_anomalies(data):
    """
    Flag anomalies based on automotive threshold rules.
    Returns the data with an 'anomaly_flag' (Int) and 'anomaly_reason' (String).
    """
    processed = data.copy()
    reasons = []

    # 1. RPM Anomaly: Check for extreme ranges or zero when moving
    rpm = processed.get('rpm', 0)
    speed = processed.get('speed', 0)
    if rpm > 6000:
        reasons.append("Extreme RPM")
    elif rpm < 500 and speed > 10:
        reasons.append("Engine Stall Risk")

    # 2. Overheating: Coolant temp > 105C
    coolant = processed.get('coolant_temp', 90)
    if coolant > 105:
        reasons.append("Overheating")

    # 3. Electrical: Battery voltage < 12.5V (Alternator) or > 15.5V (Regulator)
    voltage = processed.get('battery_voltage', 14.0)
    if voltage < 12.5:
        reasons.append("Low Voltage (Alternator Failure)")
    elif voltage > 15.5:
        reasons.append("Over-voltage (Regulator Failure)")

    # 4. Mechanical: Speed vs Throttle vs RPM mismatch
    throttle = processed.get('throttle_position', 0)
    if throttle > 90 and speed < 5 and rpm > 3000:
        reasons.append("Transmission Slip / Stuck")

    processed['anomaly_flag'] = 1 if reasons else 0
    processed['anomaly_reason'] = "; ".join(reasons) if reasons else "Normal"
    
    return processed

def transform_telemetry(raw_data):
    """Orchestrate the full transformation pipeline."""
    # Carry forward metadata
    vehicle_model = raw_data.get('vehicle_model', 'Unknown')
    vehicle_class = raw_data.get('vehicle_class', 'Unknown')
    
    data = flatten_telemetry(raw_data)
    data = parse_telemetry_types(data)
    data = detect_anomalies(data)
    
    # Ensure they are in the final dict (flatten might have missed if they were top-level)
    data['vehicle_model'] = vehicle_model
    data['vehicle_class'] = vehicle_class
    
    return data
