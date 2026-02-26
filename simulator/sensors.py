import random
import yaml
import os

def load_fleet_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'fleet_config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def load_health_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'health_config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

FLEET_CONFIG = load_fleet_config()
VEHICLE_PROFILES = FLEET_CONFIG['profiles']
VEHICLE_MODELS = FLEET_CONFIG['models']

HEALTH_CONFIG = load_health_config()
HEALTH_PROFILES = HEALTH_CONFIG['health_profiles']
FLEET_DISTRIBUTION = HEALTH_CONFIG.get('fleet_distribution', {})

from datetime import datetime

class Sensor:
    def __init__(self, name, variance, min_val=None, max_val=None, unit=""):
        self.name = name
        self.variance = variance
        self.min_val = min_val
        self.max_val = max_val
        self.unit = unit

    def emit(self, state_value, degradation=0.0, extra_noise=0.0, latent_noise=0.0):
        # Noise increases with degradation + extra (electrical) + latent (pre-failure)
        # Latent noise is more aggressive to create a "smell" of failure
        effective_variance = self.variance * (1 + (degradation * 2) + (extra_noise * 3) + (latent_noise * 10))
        noise = random.uniform(-effective_variance, effective_variance)
        
        reading = state_value + noise
        reading = self._apply_degradation(reading, degradation)
        
        # Physical constraints
        if self.min_val is not None:
            reading = max(self.min_val, reading)
        if self.max_val is not None:
            reading = min(self.max_val, reading)
            
        return round(reading, 4)

    def _apply_degradation(self, reading, degradation):
        return reading

class RPMSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        if degradation > 0:
            if random.random() < 0.05 * degradation:
                # Intermittent spikes/drops
                return reading + random.choice([-1000, 1500]) * degradation
        return reading

class CoolantTempSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        # Drift: Overheating increases linearly with degradation
        return reading + (50 * degradation)

class ThrottleSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        # Stickiness: throttle gets stuck at high values when failing
        if degradation > 0.6:
            return 80.0 + random.uniform(-5, 5)
        return reading

class BatterySensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        # Voltage drop due to cell failure or alternator wear
        if degradation > 0.3:
            return reading - (5.0 * degradation)
        return reading

class MAFSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        # MAF drift usually causes lean/rich conditions
        return reading * (1 + (0.4 * degradation * random.choice([-1, 1])))

class FuelSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        # Float stuck or sensor offset
        return reading - (10.0 * degradation)

class GPSSensor(Sensor):
    def _apply_degradation(self, reading, degradation):
        # Real GPS degradation is drift/jitter, not jumping kilometers
        if degradation > 0:
            jitter = random.uniform(-0.002, 0.002) * degradation
            return reading + jitter
        return reading

class SensorSuite:
    def __init__(self, vehicle_class="PASSENGER"):
        self.vehicle_class = vehicle_class
        self.profile = VEHICLE_PROFILES.get(vehicle_class, VEHICLE_PROFILES["PASSENGER"])
        
        # Context-aware physical floors
        batt_min = 10.5 if vehicle_class == "PASSENGER" else 21.0
        
        self.sensors = {
            "rpm": RPMSensor("RPM", 15.0, min_val=0, max_val=self.profile['max_rpm'], unit="RPM"),
            "speed": Sensor("Speed", 0.5, min_val=0, max_val=self.profile['max_speed'], unit="km/h"),
            "coolant_temp": CoolantTempSensor("Temp", 0.2, min_val=40, max_val=140, unit="C"),
            "throttle_position": ThrottleSensor("Throttle", 0.1, min_val=0, max_val=100, unit="%"),
            "battery_voltage": BatterySensor("Battery", 0.05, min_val=batt_min, unit="V"),
            "maf": MAFSensor("MAF", 0.1, min_val=0, unit="g/s"),
            "fuel_level": FuelSensor("Fuel", 0.1, min_val=0, max_val=100, unit="%"),
            "latitude": GPSSensor("Latitude", 0.00001),
            "longitude": GPSSensor("Longitude", 0.00001)
        }

    def get_readings(self, vehicle_state, health_states=None, latent_health=None):
        health_states = health_states or {}
        latent_health = latent_health or {}
        
        # Cross-sensor correlation: Battery health affects electrical noise for all sensors
        battery_degradation = health_states.get("battery_voltage", 0.0)
        electrical_noise = battery_degradation if battery_degradation > 0.2 else 0.0
        
        readings = {}
        for key, sensor in self.sensors.items():
            # Apply electrical noise to all sensors except the battery itself and GPS
            extra = electrical_noise if key not in ["battery_voltage", "latitude", "longitude"] else 0.0
            
            # Apply latent pre-failure noise
            latent = latent_health.get(key, 0.0)
            
            readings[key] = sensor.emit(
                vehicle_state.get(key, 0.0), 
                health_states.get(key, 0.0),
                extra_noise=extra,
                latent_noise=latent
            )
        return readings

    def format_telemetry(self, vehicle_id, model, state, health, timestamp=None, latent_health=None):
        """Standardises the telemetry structure according to the producer schema"""
        readings = self.get_readings(state, health, latent_health=latent_health)
        return {
            "timestamp": timestamp or datetime.now().isoformat(),
            "vehicle_id": vehicle_id,
            "vehicle_model": model,
            "vehicle_class": self.vehicle_class,
            "obd": {
                "rpm": readings["rpm"],
                "speed": readings["speed"],
                "throttle_position": readings["throttle_position"],
                "coolant_temp": readings["coolant_temp"],
                "battery_voltage": readings["battery_voltage"],
                "maf": readings["maf"],
                "fuel_level": readings["fuel_level"]
            },
            "gps": {
                "latitude": readings["latitude"],
                "longitude": readings["longitude"]
            }
        }
