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
        avg(rolling_avg_maf) as avg_maf,
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
        -- Power of 1.2 + multiplier 500 makes it VERY forgiving for the first 1-2 noise spikes
        -- but ramps up steeply if failure is persistent (>1% rate)
        least(40, pow(total_anomaly_count / total_readings, 1.2) * 500) as anomaly_penalty,

        -- 2. Thermal stress (up to 25 pts)
        -- Wide Slack: No penalty below 108C/110C to allow for heavy high-load operating range.
        -- Only genuinely overheating or degraded vehicles will hit these.
        CASE 
            WHEN vehicle_class = 'PASSENGER' THEN
                least(25, 
                    (CASE WHEN avg_coolant_temp > 108 THEN pow(avg_coolant_temp - 108, 1.8) * 5 ELSE 0 END) +
                    (CASE WHEN max_coolant_temp > 115 THEN (max_coolant_temp - 115) * 10 ELSE 0 END)
                )
            WHEN vehicle_class = 'COMMERCIAL' THEN
                least(25, 
                    (CASE WHEN avg_coolant_temp > 110 THEN pow(avg_coolant_temp - 110, 1.8) * 5 ELSE 0 END) +
                    (CASE WHEN max_coolant_temp > 117 THEN (max_coolant_temp - 117) * 10 ELSE 0 END)
                )
            ELSE 0
        END as thermal_penalty,

        -- 3. Electrical stability (up to 20 pts)
        -- Slack down to 13.2V / 25.5V to ignore natural idle-load alternator drops
        CASE
            WHEN vehicle_class = 'PASSENGER' THEN
                least(20, (CASE WHEN avg_battery_voltage < 13.2 THEN (13.2 - avg_battery_voltage) * 80 ELSE 0 END))
            WHEN vehicle_class = 'COMMERCIAL' THEN
                least(20, (CASE WHEN avg_battery_voltage < 25.5 THEN (25.5 - avg_battery_voltage) * 40 ELSE 0 END))
            ELSE 0
        END as electrical_penalty,

        -- 4. Mechanical Efficiency (up to 15 pts)
        -- Only penalize extreme efficiency outliers (heavy internal wear)
        CASE
            WHEN avg_rpm > 1000 THEN
                least(15, (CASE WHEN (avg_maf / avg_rpm) < 0.0015 THEN (0.0015 - (avg_maf / avg_rpm)) * 30000 ELSE 0 END))
            ELSE 0
        END as mechanical_penalty
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
    round(greatest(0, least(100, 100 - anomaly_penalty - thermal_penalty - electrical_penalty - mechanical_penalty)), 2) as health_score
FROM health_calculation
