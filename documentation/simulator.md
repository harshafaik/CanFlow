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
