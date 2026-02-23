{{ config(
    materialized='table',
    engine='MergeTree()',
    order_by=['vehicle_id']
) }}

WITH vehicle_metrics AS (
    SELECT
        vehicle_id,
        avg(coolant_temp) as avg_coolant_temp,
        max(coolant_temp) as max_coolant_temp,
        avg(battery_voltage) as avg_battery_voltage,
        min(battery_voltage) as min_battery_voltage,
        avg(rpm) as avg_rpm,
        sum(anomaly_flag) as total_anomaly_count,
        count(*) as total_readings,
        avg(rolling_anomaly_count) as avg_rolling_anomaly_count,
        max(coolant_temp_delta) as max_coolant_temp_delta,
        count(DISTINCT session_id) as total_sessions
    FROM {{ ref('silver_telemetry') }}
    GROUP BY vehicle_id
),

health_calculation AS (
    SELECT
        *,
        (total_anomaly_count / total_readings) as anomaly_rate,
        -- Scoring Logic: Start at 100, penalize for bad behavior
        -- Anomaly Rate Penalty (up to 50 points)
        -- Max Temp Penalty (up to 25 points if > 100C)
        -- Min Voltage Penalty (up to 25 points if < 12.5V)
        100 
        - ( (total_anomaly_count / total_readings) * 100 * 0.5 )
        - ( CASE WHEN max_coolant_temp > 100 THEN (max_coolant_temp - 100) * 5 ELSE 0 END )
        - ( CASE WHEN min_battery_voltage < 12.5 THEN (12.5 - min_battery_voltage) * 20 ELSE 0 END )
        as raw_health_score
    FROM vehicle_metrics
)

SELECT
    vehicle_id,
    avg_coolant_temp,
    max_coolant_temp,
    avg_battery_voltage,
    min_battery_voltage,
    avg_rpm,
    total_anomaly_count,
    total_readings,
    anomaly_rate,
    avg_rolling_anomaly_count,
    max_coolant_temp_delta,
    total_sessions,
    round(greatest(0, least(100, raw_health_score)), 2) as health_score
FROM health_calculation
