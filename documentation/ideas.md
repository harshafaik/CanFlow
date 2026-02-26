# Future ML Improvements & Realism Strategies

This document outlines architectural strategies for further reducing model over-optimization (AUC-ROC > 0.95) and introducing realistic "real-world" uncertainty into the CanFlow simulation and prediction engine.

## Goal: Reducing Over-Optimization
In real-world predictive maintenance, AUC-ROC scores typically range between **0.80 and 0.92**. Achieving a near-perfect score often indicates that the simulation is too "clean" or the features are too deterministic. The following strategies aim to "blur the lines" between healthy and failing vehicles.

### 1. Sensor Calibration Bias (Persistent Error)
**Concept:** Real-world IoT sensors are rarely perfectly calibrated. Every physical sensor has a persistent, unique offset.
*   **Implementation:** Assign a unique `random.uniform(-bias, +bias)` to every sensor instance upon vehicle initialization.
*   **Impact:** A healthy vehicle with a sensor biased +5°C will look identical to a slightly degraded vehicle with a perfectly calibrated sensor. This creates realistic **False Positives**.

### 2. Latent Environmental Overlap (The "Hill" Problem)
**Concept:** High engine stress is not always a sign of failure; it can be a sign of high external load (e.g., climbing a steep incline).
*   **Implementation:** Introduce a latent `incline_factor` in the simulator that scales RPM, Throttle, and Coolant Temp, but is **not** included in the telemetry schema.
*   **Impact:** A healthy vehicle climbing a 15% grade at low speed will have the same signature as a failing vehicle on flat ground. Without the "Incline" feature, the model must guess, reducing deterministic accuracy.

### 3. Data Quality & Transmission Jitter
**Concept:** Moving vehicles over cellular networks produce "messy" data—dropped packets, frozen signals, and late arrivals.
*   **Implementation:** Introduce a `data_quality_drop` probability (e.g., 2-5%) where sensor values "stick" to their last known value or return `null`.
*   **Impact:** The model loses the clean "rate-of-change" (delta) signals it currently relies on, forcing it to handle missing or stale information.

### 4. Windowed/Temporal Snapshots
**Concept:** Predicting health based on a vehicle's entire life history is "cheating." In production, models often only see a recent window of data.
*   **Implementation:** Train the XGBoost model on random 10-minute "windows" of telemetry rather than global averages from the Gold layer.
*   **Impact:** A failing vehicle may look "Fair" for 9 minutes and "Poor" for only 1 minute. If the model only sees the "Fair" window, it should realistically miss the failure (False Negative).

### 5. Hidden Driving Styles (Passive vs. Aggressive)
**Concept:** Different drivers treat vehicles differently. An aggressive driver naturally pushes a healthy engine into "hotter" operating ranges.
*   **Implementation:** Assign a hidden `driver_type` (Aggressive, Moderate, Passive) to each vehicle that acts as a multiplier for baseline heat, RPM, and throttle.
*   **Impact:** An "Aggressive" healthy driver will produce a signature that overlaps with a "Passive" driver with a failing engine, creating a mathematically inseparable boundary.
