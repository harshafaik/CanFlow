import os
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import clickhouse_connect
from dotenv import load_dotenv

# Import logic from simulator
from sensors import (
    SensorSuite,
    VEHICLE_MODELS,
    VEHICLE_PROFILES,
    HEALTH_PROFILES,
    FLEET_DISTRIBUTION,
)

# Import the transformation pipeline from stream
import sys

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "stream"))
)
from transforms import transform_telemetry

# Load environment variables
load_dotenv()


class PersistentVehicle:
    def __init__(self, vehicle_id, vehicle_model, condition="GOOD"):
        self.vehicle_id = vehicle_id
        self.vehicle_model = vehicle_model
        self.vehicle_class = VEHICLE_MODELS[vehicle_model]
        self.profile = VEHICLE_PROFILES[self.vehicle_class]
        self.sensor_suite = SensorSuite(self.vehicle_class)
        self.condition = condition

        h_profile = HEALTH_PROFILES[condition]
        self.fault_chance = h_profile["fault_chance"]
        self.wear_factor = random.uniform(*h_profile["wear_range"])
        self.recovery_speed = h_profile["recovery_speed"]
        self.fault_severity = h_profile["fault_severity"]

        self.state = {
            "rpm": self.profile["idle_rpm"] * self.wear_factor,
            "speed": 0.0,
            "coolant_temp": self.profile["avg_temp"] * self.wear_factor,
            "throttle_position": 0.0,
            "battery_voltage": self.profile["volt_baseline"],
            "maf": 5.0,
            "fuel_level": random.uniform(40.0, 100.0),
            "latitude": 19.0760 + random.uniform(-0.1, 0.1),
            "longitude": 72.8777 + random.uniform(-0.1, 0.1),
        }
        self.health = {k: 0.0 for k in self.state.keys()}

    def update(self):
        accel_max = 1.5 if self.vehicle_class == "PASSENGER" else 0.8
        acceleration = random.uniform(-1.0, accel_max)
        self.state["speed"] = max(
            0, min(self.profile["max_speed"], self.state["speed"] + acceleration)
        )

        target_rpm = (self.profile["idle_rpm"] * self.wear_factor) + (
            self.state["speed"] * (self.profile["max_rpm"] / self.profile["max_speed"])
        )
        self.state["rpm"] = max(
            self.profile["idle_rpm"] * 0.8,
            min(self.profile["max_rpm"], target_rpm + random.uniform(-50, 50)),
        )

        self.state["throttle_position"] = max(
            0,
            min(
                100,
                (self.state["speed"] / (self.profile["max_speed"] / 100))
                + random.uniform(-2, 2),
            ),
        )
        self.state["maf"] = (
            (self.state["rpm"] / 1000)
            * self.profile["maf_mult"]
            * 10
            * self.wear_factor
        )

        self.state["latitude"] += (self.state["speed"] / 360000) * random.uniform(
            0.8, 1.2
        )
        self.state["longitude"] += (self.state["speed"] / 360000) * random.uniform(
            0.8, 1.2
        )
        self.state["fuel_level"] = max(
            0, self.state["fuel_level"] - (self.state["speed"] * 0.00005)
        )

        # Fault injection severity scales with condition
        if random.random() < self.fault_chance:
            fault_sensor = random.choice(list(self.health.keys()))
            self.health[fault_sensor] = self.fault_severity

        # Recovery speed depends on vehicle condition
        for sensor in self.health:
            if self.health[sensor] > 0:
                self.health[sensor] = max(
                    0.0, self.health[sensor] - self.recovery_speed
                )

    def get_row(self, timestamp):
        readings = self.sensor_suite.get_readings(self.state, self.health)
        raw_payload = {
            "timestamp": timestamp.isoformat(),
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
                "fuel_level": readings["fuel_level"],
            },
            "gps": {
                "latitude": readings["latitude"],
                "longitude": readings["longitude"],
            },
        }
        return transform_telemetry(raw_payload)


def generate_large_fleet_data(target_rows=700000):
    available_models = list(VEHICLE_MODELS.keys())
    instances_per_model = 30

    # Target distribution from config
    conditions = []
    for cond, weight in FLEET_DISTRIBUTION.items():
        conditions.extend([cond] * weight)

    fleet = []
    for model in available_models:
        parts = model.split()
        model_short = (
            "".join([w[0] for w in parts if w[0].isupper()]) + parts[-1][1:3].upper()
        )
        v_class = VEHICLE_MODELS[model]

        for i in range(1, instances_per_model + 1):
            cond = random.choice(conditions)
            if v_class == "COMMERCIAL":
                # Commercial vehicles skew lower
                if cond == "EXCELLENT":
                    cond = "GOOD"
                elif cond == "GOOD":
                    cond = "FAIR"
                elif cond == "FAIR":
                    cond = "POOR"
                elif cond == "POOR":
                    cond = "CRITICAL"

            v_id = f"{model_short}-{i:03d}"
            fleet.append(PersistentVehicle(v_id, model, condition=cond))

    print(
        f"Initialised fleet of {len(fleet)} unique vehicles with tiered health profiles."
    )

    data = []
    iterations = (target_rows + len(fleet) - 1) // len(fleet)
    start_time = datetime.now() - timedelta(hours=12)

    for _ in range(iterations):
        for vehicle in fleet:
            start_time += timedelta(milliseconds=100)
            vehicle.update()
            data.append(vehicle.get_row(start_time))

        if len(data) % 100000 < len(fleet):
            print(f"Progress: {len(data)} rows generated...")

    return pd.DataFrame(data)


def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    parquet_path = os.path.join(root_dir, "data", "telemetry_seed.parquet")

    df = generate_large_fleet_data(target_rows=700000)
    df.to_parquet(parquet_path, index=False)

    client = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", 8124)),
        username=os.getenv("CLICKHOUSE_USER", "admin"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "password"),
        database=os.getenv("CLICKHOUSE_DATABASE", "canflow"),
    )

    client.command("TRUNCATE TABLE IF EXISTS bronze_telemetry")
    chunk_size = 100000
    for i in range(0, len(df), chunk_size):
        client.insert_df("bronze_telemetry", df.iloc[i : i + chunk_size])
        print(f"Uploaded chunk {i // chunk_size + 1}")

    print("Upload successful!")


if __name__ == "__main__":
    main()
