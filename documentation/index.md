# CanFlow Documentation

Welcome to the CanFlow project documentation. CanFlow is a high-fidelity vehicle telemetry simulator designed to emit realistic OBD-II and GPS data for fleet management and anomaly detection testing.

## Project Structure

- `simulator/`: Core simulation logic.
    - `simulator.py`: Fleet agent management and main loop.
    - `sensors.py`: Individual sensor models with noise and degradation logic.
    - `producer.py`: Kafka integration for streaming telemetry.
- `documentation/`: Project manuals and technical specs.
    - `anomalies.md`: Detailed logic for fault injection and detection.

## Getting Started

1. Activate the environment: `source .venv/bin/activate`
2. Run the simulator: `python simulator/simulator.py`

## Features

- **Multi-Agent Simulation**: Each vehicle is an independent agent.
- **Realistic Sensors**: Models variance, baseline drift, and failures.
- **Kafka Integration**: Ready to stream to a `vehicle_telemetry` topic.
