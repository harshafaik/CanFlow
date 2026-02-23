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

The `health_score` is a weighted calculation designed to prioritize immediate vehicle safety:

$$
	ext{Score} = 100 - (	ext{Anomaly Penalty}) - (	ext{Temp Penalty}) - (	ext{Voltage Penalty})
$$

- **Anomaly Penalty**: Up to 50 points based on the frequency of raw sensor flags.
- **Temp Penalty**: 5 points for every degree above 100°C.
- **Voltage Penalty**: 20 points for every volt below 12.5V (alternator failure indicator).

## Running Transformations

```bash
cd warehouse
dbt run
```
