import random
import yaml
import os

def load_fleet_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'fleet_config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

FLEET_CONFIG = load_fleet_config()
VEHICLE_PROFILES = FLEET_CONFIG['profiles']
VEHICLE_MODELS = FLEET_CONFIG['models']

class Sensor:
    def __init__(self, name, variance, unit=""):
        self.name = name
        self.variance = variance
        self.unit = unit

    def emit(self, state_value, degradation=0.0):
        noise = random.uniform(-self.variance, self.variance)
        reading = state_value + noise
        reading = self._apply_degradation(reading, degradation)
        
        # Physical constraints
        if self.name in ["Vehicle Speed", "RPM"]:
            reading = max(0, reading)
        elif self.name == "Throttle Position":
            reading = max(0, min(100, reading))
        elif self.name == "Battery Voltage":
            # Don't drop below a physical "dead battery" floor unless it's a specific failure
            # baseline is usually 12.6V or 24V
            reading = max(10.5, reading) 
            
        return round(reading, 4)

    def _apply_degradation(self, reading, degradation):
        return reading

class RPMSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        if degradation > 0:
            if random.random() < 0.1 * degradation:
                return reading + random.choice([-400, 600]) * degradation
        return reading

class CoolantTempSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        return reading + (25 * degradation)

class ThrottleSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        if degradation > 0.5:
            return 85.0 + random.uniform(-2, 2)
        return reading

class BatterySensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        return reading - (3.0 * degradation)

class MAFSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        return reading * (1 + (0.3 * degradation * random.choice([-1, 1])))

class FuelSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        return reading - (5.0 * degradation)

class GPSSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        if degradation > 0.8:
            return reading + 0.05 
        return reading

class SensorSuite:
    def __init__(self, vehicle_class="PASSENGER"):
        self.profile = VEHICLE_PROFILES.get(vehicle_class, VEHICLE_PROFILES["PASSENGER"])
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
        health_states = health_states or {}
        readings = {}
        for key, sensor in self.sensors.items():
            state_val = vehicle_state.get(key, 0.0)
            degradation = health_states.get(key, 0.0)
            readings[key] = sensor.emit(state_val, degradation)
        return readings
