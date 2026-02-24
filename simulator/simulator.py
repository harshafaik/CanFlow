import os
import time
import random
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from sensors import SensorSuite, VEHICLE_MODELS, VEHICLE_PROFILES, HEALTH_PROFILES, FLEET_DISTRIBUTION
from producer import VehicleProducer

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class VehicleAgent:
    def __init__(self, vehicle_id, vehicle_model, condition="GOOD", producer=None):
        self.vehicle_id = vehicle_id
        self.vehicle_model = vehicle_model
        self.vehicle_class = VEHICLE_MODELS.get(vehicle_model, "PASSENGER")
        self.profile = VEHICLE_PROFILES.get(self.vehicle_class)
        self.producer = producer
        self.sensor_suite = SensorSuite(self.vehicle_class)
        self.condition = condition
        
        h_profile = HEALTH_PROFILES[condition]
        self.fault_chance = h_profile['fault_chance']
        self.wear_factor = random.uniform(*h_profile['wear_range'])
        self.recovery_speed = h_profile['recovery_speed']
        self.fault_severity = h_profile['fault_severity']
        
        # Ground truth state based on profile and wear
        self.state = {
            "rpm": self.profile['idle_rpm'] * self.wear_factor,
            "speed": 0.0,
            "coolant_temp": self.profile['avg_temp'] * self.wear_factor,
            "throttle_position": 0.0,
            "battery_voltage": self.profile['volt_baseline'],
            "maf": 5.0, # Will be calculated during update
            "fuel_level": random.uniform(20.0, 100.0),
            "latitude": 19.0760 + random.uniform(-0.1, 0.1), # Expanded Mumbai start area
            "longitude": 72.8777 + random.uniform(-0.1, 0.1)
        }
        
        self.health = {k: 0.0 for k in self.state.keys()}

    def update_state(self):
        # Movement logic adjusted by class
        accel_max = 1.5 if self.vehicle_class == "PASSENGER" else 0.8
        acceleration = random.uniform(-1.0, accel_max)
        self.state["speed"] = max(0, min(self.profile['max_speed'], self.state["speed"] + acceleration))
        
        # RPM logic with wear factor
        target_rpm = (self.profile['idle_rpm'] * self.wear_factor) + \
                     (self.state["speed"] * (self.profile['max_rpm'] / self.profile['max_speed']))
        self.state["rpm"] = max(self.profile['idle_rpm'] * 0.8, min(self.profile['max_rpm'], target_rpm + random.uniform(-50, 50)))
        
        # Throttle
        self.state["throttle_position"] = max(0, min(100, (self.state["speed"] / (self.profile['max_speed']/100)) + random.uniform(-2, 2)))
        
        # MAF (Proportional to RPM and Wear)
        self.state["maf"] = (self.state["rpm"] / 1000) * self.profile['maf_mult'] * 10 * self.wear_factor
            
        # Movement
        self.state["latitude"] += (self.state["speed"] / 360000) * random.uniform(0.8, 1.2)
        self.state["longitude"] += (self.state["speed"] / 360000) * random.uniform(0.8, 1.2)
        
        # Fuel drain
        self.state["fuel_level"] = max(0, self.state["fuel_level"] - (self.state["speed"] * 0.00005))

        # Fault injection (Tiered based on condition)
        if random.random() < self.fault_chance:
            fault_sensor = random.choice(list(self.health.keys()))
            self.health[fault_sensor] = self.fault_severity
            logger.warning(f"Vehicle {self.vehicle_id} ({self.vehicle_model}): Developing fault in {fault_sensor}")

        # Recovery speed depends on vehicle condition
        for sensor in self.health:
            if self.health[sensor] > 0:
                self.health[sensor] = max(0.0, self.health[sensor] - self.recovery_speed)

    def emit_telemetry(self):
        readings = self.sensor_suite.get_readings(self.state, self.health)
        
        telemetry = {
            "timestamp": datetime.now().isoformat(),
            "vehicle_id": self.vehicle_id,
            "vehicle_model": self.vehicle_model,
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
        
        if self.producer:
            self.producer.send_reading(telemetry)
        else:
            print(json.dumps(telemetry))

def run_fleet_simulation():
    # We now ignore NUM_VEHICLES and generate based on model list + instances per model
    instances_per_model = int(os.getenv('INSTANCES_PER_MODEL', 5))
    interval = float(os.getenv('EMIT_INTERVAL_SECONDS', 1.0))

    available_models = list(VEHICLE_MODELS.keys())
    logger.info(f"Initialising fleet: {len(available_models)} models, {instances_per_model} instances each.")
    
    # Target distribution from config
    conditions = []
    for cond, weight in FLEET_DISTRIBUTION.items():
        conditions.extend([cond] * weight)
    
    producer = None
    try:
        producer = VehicleProducer()
    except Exception as e:
        logger.error(f"Producer connection error: {e}")

    fleet = []
    for model in available_models:
        model_short = "".join([w[0] for w in model.split() if w[0].isupper()])
        v_class = VEHICLE_MODELS[model]
        
        for i in range(1, instances_per_model + 1):
            cond = random.choice(conditions)
            if v_class == "COMMERCIAL":
                # Commercial vehicles skew lower
                if cond == "EXCELLENT": cond = "GOOD"
                elif cond == "GOOD": cond = "FAIR"
                elif cond == "FAIR": cond = "POOR"
                elif cond == "POOR": cond = "CRITICAL"
                
            v_id = f"{model_short}-{i:03d}"
            fleet.append(VehicleAgent(v_id, model, condition=cond, producer=producer))
    
    logger.info(f"Fleet initialised with {len(fleet)} total vehicles.")
    
    try:
        while True:
            for vehicle in fleet:
                vehicle.update_state()
                vehicle.emit_telemetry()
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Simulation stopping...")
    finally:
        if producer:
            producer.close()

if __name__ == "__main__":
    run_fleet_simulation()
