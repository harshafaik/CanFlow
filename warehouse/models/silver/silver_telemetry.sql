{{ config(
    materialized='incremental',
    unique_key=['vehicle_id', 'timestamp'],
    engine='MergeTree()',
    order_by=['vehicle_id', 'timestamp']
) }}

WITH raw_data AS (
    SELECT *
    FROM {{ source('canflow', 'bronze_telemetry') }}
    {% if is_incremental() %}
    -- Only process new data since the last run
    WHERE timestamp > (SELECT max(timestamp) FROM {{ this }})
    {% endif %}
),

windowed_features AS (
    SELECT
        *,
        -- Rolling features: last 10 readings per vehicle
        -- Note: using 0 FOLLOWING as ClickHouse alternative to CURRENT ROW
        avg(coolant_temp) OVER (PARTITION BY vehicle_id ORDER BY timestamp ROWS BETWEEN 9 PRECEDING AND 0 FOLLOWING) as rolling_avg_coolant_temp,
        avg(rpm) OVER (PARTITION BY vehicle_id ORDER BY timestamp ROWS BETWEEN 9 PRECEDING AND 0 FOLLOWING) as rolling_avg_rpm,
        avg(battery_voltage) OVER (PARTITION BY vehicle_id ORDER BY timestamp ROWS BETWEEN 9 PRECEDING AND 0 FOLLOWING) as rolling_avg_battery_voltage,
        avg(maf) OVER (PARTITION BY vehicle_id ORDER BY timestamp ROWS BETWEEN 9 PRECEDING AND 0 FOLLOWING) as rolling_avg_maf,
        avg(throttle_position) OVER (PARTITION BY vehicle_id ORDER BY timestamp ROWS BETWEEN 9 PRECEDING AND 0 FOLLOWING) as rolling_avg_throttle_position,
        
        -- Anomaly context: last 20 readings
        sum(anomaly_flag) OVER (PARTITION BY vehicle_id ORDER BY timestamp ROWS BETWEEN 19 PRECEDING AND 0 FOLLOWING) as rolling_anomaly_count,
        
        -- Rate of change using window lag (functional equivalent to neighbor with partitioning)
        coolant_temp - lagInFrame(coolant_temp) OVER (PARTITION BY vehicle_id ORDER BY timestamp) as coolant_temp_delta,
        
        -- Sessionization: check for gaps > 5 minutes (300 seconds)
        CASE 
            WHEN (timestamp - lagInFrame(timestamp) OVER (PARTITION BY vehicle_id ORDER BY timestamp)) > 300 
            OR lagInFrame(timestamp) OVER (PARTITION BY vehicle_id ORDER BY timestamp) IS NULL 
            THEN 1 
            ELSE 0 
        END as is_session_start
    FROM raw_data
),

final AS (
    SELECT
        *,
        -- unique incrementing trip ID per vehicle
        sum(is_session_start) OVER (PARTITION BY vehicle_id ORDER BY timestamp ROWS BETWEEN UNBOUNDED PRECEDING AND 0 FOLLOWING) as session_id
    FROM windowed_features
)

SELECT * FROM final
