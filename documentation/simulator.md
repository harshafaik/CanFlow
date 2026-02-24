# Simulator Component

The `simulator/simulator.py` script is the entry point for the fleet simulation. It manages multiple `VehicleAgent` instances and the overall simulation loop.

## VehicleAgent

Each `VehicleAgent` maintains a "ground truth" state (e.g., actual speed, fuel level) and uses a `SensorSuite` to emit readings that include simulated noise and potential faults.

## Simulation Loop

1. **Update State**: Each agent moves and updates its physical state (lat/lon, speed, RPM).
2. **Emit Telemetry**: Agents generate JSON telemetry using their `SensorSuite`.
3. **Kafka/Stdout**: Readings are sent to a Kafka broker if available, or printed to the console.

## Fault Injection

The simulator can randomly trigger "degradations" in sensors to simulate real-world hardware issues like sensor drift, overheating, or failure.

## Simulation Architecture

The simulation engine is built on three core components that separate physics from operational timing:

1. **`sensors.py` (The Physics)**:
   This is the shared library that defines how "Ground Truth" state is converted into "Sensor Readings." It handles natural variance, physical constraints, and the specific mathematical models for sensor degradation (e.g., how much extra heat an overheating fault adds).

2. **`simulator.py` (The "Now")**:
   The production engine designed for real-time streaming. It uses a persistent loop with `time.sleep()` to emit telemetry to Kafka/Redpanda at a human-readable pace. It treats the fleet as a live, evolving system.

3. **`seed_generator.py` (The "Past")**:
   The analytics engine designed for batch processing. It uses the same physics as the real-time simulator but manually increments synthetic timestamps (e.g., in 100ms steps) to generate months of historical data in a few seconds. This data is written directly to Parquet and ClickHouse to provide a rich baseline for dbt models and dashboards.

By sharing `sensors.py`, both the live stream and the historical seed data maintain identical fault signatures and physical behaviors.
