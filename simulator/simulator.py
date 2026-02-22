import time
import random
import json
import logging
from datetime import datetime
from sensors import SensorSuite
from producer import VehicleProducer

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class VehicleAgent:
    def __init__(self, vehicle_id, producer=None):
        self.vehicle_id = vehicle_id
        self.producer = producer
        self.sensor_suite = SensorSuite()
        
        # Ground truth state
        self.state = {
            "rpm": 800.0,
            "speed": 0.0,
            "coolant_temp": 88.0,
            "throttle_position": 0.0,
            "battery_voltage": 14.1,
            "maf": 5.0,
            "fuel_level": 100.0,
            "latitude": 37.7749 + random.uniform(-0.01, 0.01),
            "longitude": -122.4194 + random.uniform(-0.01, 0.01)
        }
        
        # Health states for each sensor (0.0 = healthy, 1.0 = failed)
        self.health = {
            "rpm": 0.0,
            "speed": 0.0,
            "coolant_temp": 0.0,
            "throttle_position": 0.0,
            "battery_voltage": 0.0,
            "maf": 0.0,
            "fuel_level": 0.0,
            "latitude": 0.0,
            "longitude": 0.0
        }

    def update_state(self):
        """Update the underlying 'ground truth' of the vehicle."""
        # Simple movement simulation
        acceleration = random.uniform(-1, 2)
        self.state["speed"] = max(0, min(120, self.state["speed"] + acceleration))
        
        # RPM roughly follows speed with some base idle
        target_rpm = 800 + (self.state["speed"] * 40)
        self.state["rpm"] = max(800, min(6500, target_rpm + random.uniform(-50, 50)))
        
        # Throttle follows speed
        self.state["throttle_position"] = max(0, min(100, (self.state["speed"] / 1.2) + random.uniform(-2, 2)))
        
        # Fuel drain (very slow)
        self.state["fuel_level"] = max(0, self.state["fuel_level"] - (self.state["speed"] * 0.0001))
        
        # Coordinate movement
        self.state["latitude"] += (self.state["speed"] / 360000) * random.uniform(0.8, 1.2)
        self.state["longitude"] += (self.state["speed"] / 360000) * random.uniform(0.8, 1.2)

        # Randomly trigger a degradation (for demo)
        if random.random() < 0.005:
            fault_sensor = random.choice(list(self.health.keys()))
            self.health[fault_sensor] = min(1.0, self.health[fault_sensor] + 0.2)
            logger.warning(f"Vehicle {self.vehicle_id}: Fault developing in {fault_sensor}")

    def emit_telemetry(self):
        """Produce readings via sensor suite and send to producer."""
        readings = self.sensor_suite.get_readings(self.state, self.health)
        
        telemetry = {
            "timestamp": datetime.now().isoformat(),
            "vehicle_id": self.vehicle_id,
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

def run_fleet_simulation(num_vehicles=5, kafka_bootstrap=['localhost:9092']):
    logger.info(f"Initialising simulation for {num_vehicles} vehicles...")
    
    producer = None
    try:
        producer = VehicleProducer(bootstrap_servers=kafka_bootstrap)
    except Exception as e:
        logger.error(f"Could not connect to Kafka: {e}. Outputting to stdout only.")

    fleet = [VehicleAgent(f"VEHICLE_{i:03d}", producer=producer) for i in range(num_vehicles)]
    
    try:
        while True:
            for vehicle in fleet:
                vehicle.update_state()
                vehicle.emit_telemetry()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Simulation stopping...")
    finally:
        if producer:
            producer.close()

if __name__ == "__main__":
    run_fleet_simulation(num_vehicles=3)
