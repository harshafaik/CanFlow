# Anomaly Detection Logic

CanFlow employs a **two-stage logic** for generating and detecting vehicle anomalies. This architecture separates the *cause* (physical failure) from the *effect* (telemetry detection), mirroring real-world automotive diagnostics.

## Stage 1: Probabilistic Fault Injection (Cause)
*Location: `simulator/seed_generator.py`, `simulator/simulator.py`, and `config/health_config.yaml`*

Anomalies originate in the simulation layer as physical degradations to the vehicle's "Ground Truth" state.

1.  **Trigger**: Based on a vehicle's assigned health profile (from **EXCELLENT** to **CRITICAL**), a `fault_chance` determines if a fault is injected during any given simulation step.
2.  **Mechanism**: When a fault is triggered, a random sensor (e.g., `coolant_temp`) is assigned a `fault_severity` value in the vehicle's internal `health` state.
3.  **Persistence**: Faults are temporal rather than binary. They "recover" (decay toward 0.0) at a `recovery_speed` defined in the configuration. This simulates intermittent issues or parts that fail and then stabilize.
4.  **Physical Impact**: The `SensorSuite` in `simulator/sensors.py` applies these health offsets to the raw state. For example, a 1.0 severity fault in a `CoolantTempSensor` results in a $+40^\circ C$ swing, pushing the reading into a dangerous range.

## Stage 2: Rule-based Detection (Effect)
*Location: `stream/transforms.py`*

The transformation pipeline acts as a "Virtual Technician" that monitors the raw telemetry stream and flags issues based on deterministic automotive thresholds. This layer has no visibility into the simulator's internal health state.

1.  **Deterministic Rules**: The `detect_anomalies` function applies hard thresholds to the incoming data:
    *   **Thermal**: Coolant Temp $> 115^\circ C$.
    *   **Electrical**: Voltage outside bounds (e.g., $< 11.5V$ or $> 16V$ for passenger vehicles).
    *   **Mechanical**: Extreme RPM ($> 7000$) or Transmission Slip (High RPM + High Throttle + Low Speed).
2.  **Flagging**: If any rule is violated, the `anomaly_flag` is set to `1` and the specific violation reasons (e.g., "Overheating; Low Voltage") are concatenated into the `anomaly_reason` field.

## Summary Comparison

| Feature | Stage 1: Simulator (Injection) | Stage 2: Stream (Detection) |
| :--- | :--- | :--- |
| **Role** | **Cause** | **Effect** |
| **Nature** | Probabilistic & Temporal | Deterministic & Instantaneous |
| **Logic Source** | `health_config.yaml` | `transforms.py` thresholds |
| **Visibility** | Internal "Health" state | Raw Sensor "Readings" |

This separation ensures that the ingestion and analytics layers must rely purely on sensor data to "discover" failures, providing a high-fidelity testbed for developing predictive maintenance algorithms.
