# Data Transformations (dbt)

CanFlow uses **dbt (data build tool)** to transform raw telemetry in ClickHouse through a Medallion Architecture (Bronze $ightarrow$ Silver $ightarrow$ Gold).

## Medallion Architecture

### 1. Bronze Layer (`bronze_telemetry`)
- **Nature**: Raw ingestion from Kafka.
- **Content**: Unmodified, flattened JSON payloads.
- **Provider**: `stream/writer.py`.

### 2. Silver Layer (`silver_telemetry`)
- **Materialization**: `incremental` (optimized for high-volume append-only data).
- **Key Features**:
    - **Rolling Averages**: 10-reading windows for `coolant_temp`, `rpm`, and `battery_voltage`.
    - **Rate of Change**: `coolant_temp_delta` calculated using `lagInFrame` to detect sudden spikes.
    - **Anomaly Context**: `rolling_anomaly_count` (sum of flags over last 20 readings).
    - **Sessionization**: Gaps in telemetry $> 5$ minutes trigger a new `session_id`, allowing trip-based analysis.

### 3. Gold Layer (`gold_vehicle_health`)
- **Materialization**: `table` (full refresh for latest fleet status).
- **Purpose**: Executive-level fleet health monitoring.
- **Metrics**:
    - `anomaly_rate`: Percentage of readings flagged as anomalous.
    - `max_coolant_temp_delta`: Peak rate of temperature change (predictive of engine stress).
    - `health_score`: A composite metric (0-100).

## Health Score Formula

The `health_score` is a weighted, non-linear calculation (0-100) designed to prioritize immediate vehicle safety while ignoring normal high-load operating fluctuations:

$$
\text{Score} = 100 - (\text{Anomaly Penalty}) - (\text{Thermal Penalty}) - (\text{Electrical Penalty}) - (\text{Mechanical Penalty})
$$

- **Anomaly Penalty (Max 40 pts)**: Non-linear penalty that scales with the frequency of raw sensor flags. Uses `pow(rate, 1.2)` to be forgiving of isolated noise while penalizing persistent failures.
- **Thermal Penalty (Max 25 pts)**: Context-aware thresholds (Passenger: 108°C, Commercial: 110°C). Penalties scale exponentially using `pow(delta, 1.8)` once the "dead zone" is breached.
- **Electrical Penalty (Max 20 pts)**: Penalizes low voltage (Alternator failure) with slack for natural idle-load drops (Passenger: 13.2V, Commercial: 25.5V).
- **Mechanical Penalty (Max 15 pts)**: Detects extreme internal wear by monitoring efficiency outliers (`MAF / RPM` ratio).

## Running Transformations

```bash
cd warehouse
dbt run
```
