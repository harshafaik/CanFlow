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
    Flag anomalies based on automotive threshold rules and cross-sensor correlations.
    Returns the data with an 'anomaly_flag' (Int) and 'anomaly_reason' (String).
    """
    processed = data.copy()
    reasons = []
    
    vehicle_class = processed.get('vehicle_class', 'PASSENGER')
    rpm = processed.get('rpm', 0)
    speed = processed.get('speed', 0)
    voltage = processed.get('battery_voltage', 14.0)
    coolant = processed.get('coolant_temp', 90)
    throttle = processed.get('throttle_position', 0)
    maf = processed.get('maf', 0)

    # 1. RPM Anomaly: Context-aware limits (Commercial vs Passenger)
    rpm_limit = 6500 if vehicle_class == 'PASSENGER' else 4200
    if rpm > rpm_limit:
        reasons.append("Extreme RPM")
    elif rpm < 500 and speed > 10:
        reasons.append("Engine Stall Risk")

    # 2. Overheating: Coolant temp > 115C
    if coolant > 115:
        reasons.append("Overheating")

    # 3. Electrical: Context-aware battery voltage thresholds
    if vehicle_class == 'COMMERCIAL':
        if voltage < 22.0:
            reasons.append("Low Voltage (Alternator Failure)")
        elif voltage > 30.0:
            reasons.append("Over-voltage (Regulator Failure)")
    else: # Passenger / Standard 12V
        if voltage < 11.5:
            reasons.append("Low Voltage (Alternator Failure)")
        elif voltage > 16.0:
            reasons.append("Over-voltage (Regulator Failure)")

    # 4. Correlation Rule: MAF vs RPM (Plausibility)
    # If engine is spinning fast (>2500) but air flow is near zero, MAF is failing
    if rpm > 2500 and maf < 2.0:
        reasons.append("MAF Sensor Failure / Implausibility")

    # 5. Mechanical: Speed vs Throttle vs RPM mismatch (Transmission Slip)
    # Lowered throttle to 75% to catch the "Stuck Throttle" failure mode (>0.6 degradation)
    if throttle > 75 and speed < 5 and rpm > 2500:
        reasons.append("Transmission Slip / Stuck Throttle")

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
