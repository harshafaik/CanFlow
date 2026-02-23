import os
import random
import yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import clickhouse_connect
from dotenv import load_dotenv

# Import logic from simulator
from sensors import SensorSuite, VEHICLE_MODELS, VEHICLE_PROFILES

# Load environment variables
load_dotenv()

class PersistentVehicle:
    """A wrapper for VehicleAgent-like state but for batch generation."""
    def __init__(self, vehicle_id, vehicle_model):
        self.vehicle_id = vehicle_id
        self.vehicle_model = vehicle_model
        self.vehicle_class = VEHICLE_MODELS[vehicle_model]
        self.profile = VEHICLE_PROFILES[self.vehicle_class]
        self.sensor_suite = SensorSuite(self.vehicle_class)
        
        # Initial State
        self.state = {
            "rpm": self.profile['idle_rpm'],
            "speed": 0.0,
            "coolant_temp": self.profile['avg_temp'],
            "throttle_position": 0.0,
            "battery_voltage": self.profile['volt_baseline'],
            "maf": 5.0,
            "fuel_level": 100.0,
            "latitude": 19.0760 + random.uniform(-0.05, 0.05),
            "longitude": 72.8777 + random.uniform(-0.05, 0.05)
        }
        self.health = {k: 0.0 for k in self.state.keys()}

    def update(self):
        # Accelerate or decelerate
        accel_max = 1.5 if self.vehicle_class == "PASSENGER" else 0.8
        acceleration = random.uniform(-1.0, accel_max)
        self.state["speed"] = max(0, min(self.profile['max_speed'], self.state["speed"] + acceleration))
        
        # RPM logic
        target_rpm = self.profile['idle_rpm'] + (self.state["speed"] * (self.profile['max_rpm'] / self.profile['max_speed']))
        self.state["rpm"] = max(self.profile['idle_rpm'], min(self.profile['max_rpm'], target_rpm + random.uniform(-50, 50)))
        
        # Throttle
        self.state["throttle_position"] = max(0, min(100, (self.state["speed"] / (self.profile['max_speed']/100)) + random.uniform(-2, 2)))
        
        # MAF
        self.state["maf"] = (self.state["rpm"] / 1000) * self.profile['maf_mult'] * 10
        
        # Movement
        self.state["latitude"] += (self.state["speed"] / 360000) * random.uniform(0.8, 1.2)
        self.state["longitude"] += (self.state["speed"] / 360000) * random.uniform(0.8, 1.2)
        
        # Fuel drain
        self.state["fuel_level"] = max(0, self.state["fuel_level"] - (self.state["speed"] * 0.00005))

    def get_row(self, timestamp):
        readings = self.sensor_suite.get_readings(self.state, self.health)
        return {
            'timestamp': timestamp,
            'vehicle_id': self.vehicle_id,
            'vehicle_model': self.vehicle_model,
            'vehicle_class': self.vehicle_class,
            'rpm': readings['rpm'],
            'speed': readings['speed'],
            'throttle_position': readings['throttle_position'],
            'coolant_temp': readings['coolant_temp'],
            'battery_voltage': readings['battery_voltage'],
            'maf': readings['maf'],
            'fuel_level': readings['fuel_level'],
            'latitude': readings['latitude'],
            'longitude': readings['longitude'],
            'anomaly_flag': 0,
            'anomaly_reason': 'Normal'
        }

def generate_ice_fleet_data(num_rows=10000):
    # Filter only ICE models (Exclude EV class)
    ice_models = [m for m, c in VEHICLE_MODELS.items() if c != "EV"]
    
    fleet = []
    for _ in range(15): # 15 unique vehicles
        model = random.choice(ice_models)
        fleet.append(PersistentVehicle(f"IND-{random.randint(1000, 9999)}", model))

    data = []
    start_time = datetime.now() - timedelta(hours=2)
    
    # Simulate time-series properly per vehicle
    for _ in range(num_rows // len(fleet)):
        for vehicle in fleet:
            start_time += timedelta(seconds=1)
            vehicle.update()
            data.append(vehicle.get_row(start_time))

    return pd.DataFrame(data)

def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    parquet_path = os.path.join(root_dir, 'data', 'telemetry_seed.parquet')
    
    print(f"Generating high-fidelity ICE telemetry data...")
    df = generate_ice_fleet_data(num_rows=10000)
    
    print(f"Saving to Parquet: {parquet_path}")
    df.to_parquet(parquet_path, index=False)
    
    # ClickHouse Config
    host = os.getenv('CLICKHOUSE_HOST', 'localhost')
    port = int(os.getenv('CLICKHOUSE_PORT', 8124))
    user = os.getenv('CLICKHOUSE_USER', 'admin')
    password = os.getenv('CLICKHOUSE_PASSWORD', 'password')
    database = os.getenv('CLICKHOUSE_DATABASE', 'canflow')
    
    print(f"Connecting to ClickHouse at {host}:{port}...")
    try:
        client = clickhouse_connect.get_client(
            host=host, port=port, username=user, password=password, database=database
        )
        
        # Clean current table to avoid duplicate messy test data
        client.command("TRUNCATE TABLE IF EXISTS bronze_telemetry")
        
        print(f"Uploading fresh high-fidelity data to bronze_telemetry...")
        client.insert_df('bronze_telemetry', df)
        print(f"Upload successful! Total rows: {len(df)}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
