# Machine Learning & Risk Prediction

This document outlines the evolution of the Vehicle Risk Prediction model, the challenges of working with synthetic data, and the path to achieving a realistic predictive system.

## The Challenge: The "Perfect" Model Fallacy

Initially, the XGBoost model achieved an **AUC-ROC score of 1.0000**. While statistically perfect, this indicated a critical flaw in the machine learning design: **Label Leakage**.

### The Root Cause: Deterministic Leakage
In the first iteration, the model was "cheating" by observing the exact same variables used to calculate the ground truth health score.
*   **The Target:** `is_at_risk` was derived from a linear SQL formula in the Gold layer.
*   **The Features:** The model was given the exact averages (e.g., `avg_coolant_temp`) used in that formula.
*   **The Result:** The model didn't learn mechanical failure patterns; it simply reverse-engineered the SQL thresholds.

## Step 1: Implementing "Digital Twin" Physics

To break the deterministic link, we refactored the simulator to move from random offsets to a physics-based correlation engine.

### Key Physical Correlations
1.  **Air Flow (MAF):** Realistically scales with both **RPM and Throttle Position**.
2.  **Thermal Dynamics:** Engine temperature is now a function of **Engine Load**. High RPMs under heavy throttle cause the coolant temperature to rise above average.
3.  **Alternator Charging:** Battery voltage fluctuations are tied to RPM, simulating the alternator's charging cycle.

## Step 2: Breaking the Leakage

### Latent Factors (Hidden Variables)
We introduced "Latent Factors" that affect the sensors but are **not** provided to the model:
*   **Ambient Temperature:** A hidden weather variable that offsets engine heat. The model must now distinguish between "Normal high heat" (a hot day) and "Anomalous high heat" (engine failure).
*   **Latent Pre-Failure Noise:** Added a "latent instability" state where sensors begin to "smell bad" (increased jitter) before they actually trigger a hard anomaly.

### Feature Engineering (Moving to Snapshots)
We removed the "Smoking Gun" features from `train.py`:
*   **Removed:** `avg_coolant_temp` and `avg_battery_voltage` (The direct SQL inputs).
*   **Added:** `maf_rpm_ratio` (Efficiency), `volt_volatility` (Electrical stability), and `max_coolant_temp_delta` (Thermal rate of change).

## Step 3: Elastic Scoring in the Gold Layer

To prevent a "Data Swamp" where 70% of vehicles were marked as "Fair," we implemented **Elastic Scoring**:
*   **Dead Zones:** No penalties are applied for normal physical fluctuations (e.g., up to 108°C under load).
*   **Exponential Scaling:** Penalties for degraded vehicles now scale non-linearly (`pow(delta, 1.8)`), ensuring that truly failing vehicles are clearly separated from healthy ones.

## Final Result: Realistic Predictive Power

After these refactors, the XGBoost model achieved a realistic **AUC-ROC Score of 0.9786**.

| Metric | Result |
| :--- | :--- |
| **Accuracy** | 94% |
| **Healthy (N)** | 446 |
| **At-Risk (N)** | 178 |
| **AUC-ROC** | 0.9786 |

### Why this matters
The model is now learning **latent mechanical signatures** rather than simple thresholds. It can identify a vehicle as "At-Risk" even before it triggers a hard anomaly by observing subtle changes in efficiency ratios and sensor volatility—exactly how a production-grade predictive maintenance system operates.
