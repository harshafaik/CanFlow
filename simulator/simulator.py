import os
import time
import random
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from sensors import SensorSuite, VEHICLE_MODELS, VEHICLE_PROFILES
from producer import VehicleProducer

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class VehicleAgent:
    def __init__(self, vehicle_id, vehicle_model, producer=None):
        self.vehicle_id = vehicle_id
        self.vehicle_model = vehicle_model
        self.vehicle_class = VEHICLE_MODELS.get(vehicle_model, "PASSENGER")
        self.profile = VEHICLE_PROFILES.get(self.vehicle_class)
        self.producer = producer
        self.sensor_suite = SensorSuite(self.vehicle_class)
        
        # Ground truth state based on profile
        self.state = {
            "rpm": self.profile['idle_rpm'],
            "speed": 0.0,
            "coolant_temp": self.profile['avg_temp'],
            "throttle_position": 0.0,
            "battery_voltage": self.profile['volt_baseline'],
            "maf": 5.0 if self.vehicle_class != "EV" else 0.0,
            "fuel_level": 100.0,
            "latitude": 19.0760 + random.uniform(-0.05, 0.05), # Start around Mumbai
            "longitude": 72.8777 + random.uniform(-0.05, 0.05)
        }
        
        self.health = {k: 0.0 for k in self.state.keys()}

    def update_state(self):
        # Movement logic adjusted by class
        accel_max = 3.0 if self.vehicle_class == "EV" else (1.5 if self.vehicle_class == "PASSENGER" else 0.8)
        acceleration = random.uniform(-1.0, accel_max)
        self.state["speed"] = max(0, min(self.profile['max_speed'], self.state["speed"] + acceleration))
        
        # RPM logic
        if self.vehicle_class == "EV":
            self.state["rpm"] = self.state["speed"] * 100 # Simple motor RPM
        else:
            target_rpm = self.profile['idle_rpm'] + (self.state["speed"] * (self.profile['max_rpm'] / self.profile['max_speed']))
            self.state["rpm"] = max(self.profile['idle_rpm'], min(self.profile['max_rpm'], target_rpm + random.uniform(-50, 50)))
        
        self.state["throttle_position"] = max(0, min(100, (self.state["speed"] / (self.profile['max_speed']/100)) + random.uniform(-2, 2)))
        
        # MAF (Proportional to RPM for ICE)
        if self.vehicle_class != "EV":
            self.state["maf"] = (self.state["rpm"] / 1000) * self.profile['maf_mult'] * 10
            
        self.state["latitude"] += (self.state["speed"] / 360000) * random.uniform(0.8, 1.2)
        self.state["longitude"] += (self.state["speed"] / 360000) * random.uniform(0.8, 1.2)

        if random.random() < 0.001:
            fault_sensor = random.choice(list(self.health.keys()))
            self.health[fault_sensor] = min(1.0, self.health[fault_sensor] + 0.2)
            logger.warning(f"Vehicle {self.vehicle_id} ({self.vehicle_model}): Fault in {fault_sensor}")

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
    num_vehicles = int(os.getenv('NUM_VEHICLES', 5))
    interval = float(os.getenv('EMIT_INTERVAL_SECONDS', 1.0))

    logger.info(f"Initialising fleet of {num_vehicles} diverse vehicles...")
    
    producer = None
    try:
        producer = VehicleProducer()
    except Exception as e:
        logger.error(f"Producer error: {e}")

    # Randomly select models for the fleet (ICE only)
    available_models = [m for m, c in VEHICLE_MODELS.items() if c != "EV"]
    fleet = []
    for i in range(num_vehicles):
        model = random.choice(available_models)
        fleet.append(VehicleAgent(f"IND-{random.randint(1000,9999)}", model, producer=producer))
    
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
