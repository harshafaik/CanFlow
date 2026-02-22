# Producer Component

The `simulator/producer.py` module handles the communication between the simulator and the Kafka broker.

## VehicleProducer

The `VehicleProducer` class uses `kafka-python` to send serialized vehicle telemetry JSON objects to a specific topic.

## Configuration

- **Bootstrap Servers**: Default is `['localhost:9092']`.
- **Topic**: Default is `vehicle_telemetry`.
- **Acks**: Set to `'all'` for reliability.
- **Retries**: Configured with 5 retries to handle transient failures.

## Connection Lifecycle

The producer attempts to connect on initialization. If a broker is not found, it logs a warning and drops readings to avoid crashing the simulation.
