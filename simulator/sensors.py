import random

class Sensor:
    def __init__(self, name, variance, unit=""):
        self.name = name
        self.variance = variance
        self.unit = unit

    def emit(self, state_value, degradation=0.0):
        """
        state_value: The ground truth value from the vehicle.
        degradation: 0.0 (healthy) to 1.0 (failed).
        """
        noise = random.uniform(-self.variance, self.variance)
        reading = state_value + noise
        return round(self._apply_degradation(reading, degradation), 4)

    def _apply_degradation(self, reading, degradation):
        return reading

class RPMSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        if degradation > 0:
            # Misfire (drops) or Idle Surge (spikes)
            if random.random() < 0.1 * degradation:
                return reading + random.choice([-400, 600]) * degradation
        return reading

class CoolantTempSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        # Overheating: steady climb
        return reading + (25 * degradation)

class ThrottleSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        # Stuck throttle: ignores state_value and stays high
        if degradation > 0.5:
            return 85.0 + random.uniform(-2, 2)
        return reading

class BatterySensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        # Alternator failure: voltage drops
        return reading - (3.0 * degradation)

class MAFSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        # Sensor drift: offset becomes increasingly inaccurate
        return reading * (1 + (0.3 * degradation * random.choice([-1, 1])))

class FuelSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        # Abnormal consumption: faster drain (handled by state usually, but here as a reading offset)
        return reading - (5.0 * degradation)

class GPSSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        # Geofence breach or spoofing (offsetting location)
        if degradation > 0.8:
            return reading + 0.05 # Large jump
        return reading

class SensorSuite:
    def __init__(self):
        self.sensors = {
            "rpm": RPMSensor("RPM", variance=15.0, unit="RPM"),
            "speed": Sensor("Vehicle Speed", variance=0.5, unit="km/h"),
            "coolant_temp": CoolantTempSensor("Coolant Temp", variance=0.2, unit="C"),
            "throttle_position": ThrottleSensor("Throttle Position", variance=0.1, unit="%"),
            "battery_voltage": BatterySensor("Battery Voltage", variance=0.05, unit="V"),
            "maf": MAFSensor("MAF", variance=0.1, unit="g/s"),
            "fuel_level": FuelSensor("Fuel Level", variance=0.1, unit="%"),
            "latitude": GPSSensor("Latitude", variance=0.00001),
            "longitude": GPSSensor("Longitude", variance=0.00001)
        }

    def get_readings(self, vehicle_state, health_states=None):
        """
        vehicle_state: dict of ground truth values.
        health_states: dict of degradation levels (0.0 to 1.0) per sensor.
        """
        health_states = health_states or {}
        readings = {}
        for key, sensor in self.sensors.items():
            state_val = vehicle_state.get(key, 0.0)
            degradation = health_states.get(key, 0.0)
            readings[key] = sensor.emit(state_val, degradation)
        return readings
