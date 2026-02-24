{{ config(
    materialized='table',
    engine='MergeTree()',
    order_by=['vehicle_id']
) }}

WITH vehicle_metrics AS (
    SELECT
        vehicle_id,
        any(vehicle_model) as vehicle_model,
        any(vehicle_class) as vehicle_class,
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
        
        -- 1. Non-linear Anomaly Penalty (up to 40 pts)
        -- A small rate (1%) costs ~10pts, while higher rates scale up non-linearly
        least(40, pow(total_anomaly_count / total_readings, 0.5) * 100) as anomaly_penalty,

        -- 2. Continuous Thermal stress (up to 30 pts)
        -- Penalize every degree above the ideal baseline (90C Passenger / 92C Commercial)
        -- This ensures vehicles with high wear factors lose points even without anomalies
        CASE 
            WHEN vehicle_class = 'PASSENGER' THEN
                least(30, 
                    (CASE WHEN avg_coolant_temp > 90 THEN (avg_coolant_temp - 90) * 5 ELSE 0 END) +
                    (CASE WHEN max_coolant_temp > 105 THEN (max_coolant_temp - 105) * 2 ELSE 0 END)
                )
            WHEN vehicle_class = 'COMMERCIAL' THEN
                least(30, 
                    (CASE WHEN avg_coolant_temp > 92 THEN (avg_coolant_temp - 92) * 5 ELSE 0 END) +
                    (CASE WHEN max_coolant_temp > 107 THEN (max_coolant_temp - 107) * 2 ELSE 0 END)
                )
            ELSE 0
        END as thermal_penalty,

        -- 3. Electrical stability (up to 30 pts)
        -- Penalize any drop from baseline (14.2V Passenger / 26.5V Commercial)
        CASE
            WHEN vehicle_class = 'PASSENGER' THEN
                least(30, (CASE WHEN avg_battery_voltage < 14.2 THEN (14.2 - avg_battery_voltage) * 50 ELSE 0 END))
            WHEN vehicle_class = 'COMMERCIAL' THEN
                least(30, (CASE WHEN avg_battery_voltage < 26.5 THEN (26.5 - avg_battery_voltage) * 20 ELSE 0 END))
            ELSE 0
        END as electrical_penalty
    FROM vehicle_metrics
)

SELECT
    vehicle_id,
    vehicle_model,
    vehicle_class,
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
    round(greatest(0, least(100, 100 - anomaly_penalty - thermal_penalty - electrical_penalty)), 2) as health_score
FROM health_calculation
