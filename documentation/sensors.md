# Sensors Component

The `simulator/sensors.py` module defines the logic for individual sensors, including their baselines, natural variance, and degradation models.

## Sensor Types

- **RPMSensor**: Natural noise around RPM; simulates misfires (spikes/drops) on degradation.
- **CoolantTempSensor**: Steady temperature; simulates overheating on degradation.
- **ThrottleSensor**: 0-100% range; simulates stuck throttle on degradation.
- **BatterySensor**: Battery voltage; simulates alternator failure on degradation.
- **MAFSensor**: Airflow sensor; simulates sensor drift on degradation.
- **FuelSensor**: 0-100% range; simulates abnormal consumption on degradation.
- **GPSSensor**: Location; simulates geofence breaches or spoofing on degradation.

## SensorSuite

The `SensorSuite` class aggregates all sensor models and provides a single method to emit a batch of readings given the vehicle's ground truth state and health.
