# Known Issues & Troubleshooting

This document tracks technical hurdles encountered during the development of CanFlow and their respective resolutions.

## 1. Confluent Schema Registry Incompatibility (409 Conflict)

### Issue
When updating the `VehicleProducer` to include schema validation, a `409 Conflict` error was returned by Confluent Cloud.
```text
Error producing message: Schema being registered is incompatible with an earlier schema for subject "vehicle.telemetry.raw-value"
```

### Cause
The initial auto-generated schema in Confluent Cloud did not define any fields as `required`. The updated local schema explicitly added a `required: [...]` array. Under `BACKWARD` compatibility rules (the default), adding a required field is considered a breaking change because old producers (which don't know about the requirement) would produce invalid data according to the new schema.

### Resolution
The local JSON schema string was modified to remove the `required` constraints, matching the loose structure of the Version 1 schema already residing in the Registry.

---

## 2. JSONDeserializer Strict Constructor Signature

### Issue
The `confluent-kafka` Python library's `JSONDeserializer` threw multiple `TypeError` and `ValueError` during initialization.
```text
ValueError: from_dict must be callable with the signature from_dict(dict, SerializationContext) -> object
```

### Cause
The `JSONDeserializer` constructor is highly sensitive to positional arguments and the signature of the `from_dict` hook:
1. It expects a callable for `from_dict` that accepts exactly two arguments: the dictionary and the `SerializationContext`.
2. Passing the `SchemaRegistryClient` as a positional argument was causing it to be misinterpreted as the `from_dict` hook.

### Resolution
1. Defined an explicit helper function `dict_to_telemetry(obj, ctx)` to satisfy the two-argument requirement.
2. Used **explicit keyword arguments** during initialization to ensure parameters were mapped correctly:
   ```python
   self.json_deserializer = JSONDeserializer(
       schema_str=schema_str,
       from_dict=dict_to_telemetry,
       schema_registry_client=self.schema_registry_client
   )
   ```

---

## 3. Bronze Table Schema Mismatch (Unrecognized Column)

### Issue
The stream consumer failed to flush data to ClickHouse with the following error:
```text
ERROR:writer:Failed to flush to ClickHouse: Unrecognized column 'anomaly_reason' in table bronze_telemetry
```

### Cause
The `bronze_telemetry` table was previously created with an older schema that did not include the `anomaly_reason` field. Since the `stream/transforms.py` pipeline was now producing this field, the ClickHouse `INSERT` statement (which includes all keys from the transformed dictionary) failed because the table structure was outdated.

### Resolution
The `bronze_telemetry` table was manually dropped:
```sql
DROP TABLE IF EXISTS bronze_telemetry;
```
Upon the next run of the `stream/consumer.py`, the `ClickHouseWriter` automatically recreated the table using the up-to-date schema defined in its `_ensure_table` method, which includes both `anomaly_flag` and `anomaly_reason`.

---

## 4. ClickHouseWriter Threading Deadlock

### Issue
The `stream/consumer.py` would connect to Kafka and receive messages, but data would never appear in ClickHouse. The process appeared to hang indefinitely after reaching the buffer threshold.

### Cause
In `stream/writer.py`, the `add()` method acquired a standard `threading.Lock()` and then called `self.flush()`. The `flush()` method also attempted to acquire the same lock. Since `threading.Lock` is non-reentrant, the thread deadlocked itself.

### Resolution
The lock type was changed from `threading.Lock()` to `threading.RLock()` (Re-entrant Lock). This allows the same thread to acquire the lock multiple times, enabling `add()` to safely call `flush()` while still protecting the buffer from the background periodic flush thread.

---

## 5. ClickHouse Window Function Syntax (CURRENT ROW)

### Issue
When attempting to run a rolling average window function, ClickHouse threw a syntax error:
```sql
SELECT 
    vehicle_id,
    avg(coolant_temp) OVER (PARTITION BY vehicle_id ORDER BY timestamp ROWS BETWEEN 9 PRECEDING AND CURRENT ROW)
FROM canflow.bronze_telemetry;
```
**Error:** `Code: 62. DB::Exception: Syntax error: failed at position 111 (and) ... Expected one of: ... token, ClosingRoundBracket, end of query.`

### Cause
While ClickHouse supports window functions, its SQL parser can be strict or behave differently regarding specific frame boundary keywords like `CURRENT ROW` in certain contexts compared to standard PostgreSQL or BigQuery dialects.

### Resolution
Use `0 FOLLOWING` as a functional equivalent to `CURRENT ROW` when defining the frame boundary:
```sql
SELECT 
    vehicle_id,
    avg(coolant_temp) OVER (PARTITION BY vehicle_id ORDER BY timestamp ROWS BETWEEN 9 PRECEDING AND 0 FOLLOWING) as rolling_avg_coolant
FROM canflow.bronze_telemetry;
```
This syntax is explicitly recognized by the ClickHouse parser and produces the correct rolling window result.

---

## 6. Schema Evolution: Adding Top-Level Properties

### Issue
When attempting to add `vehicle_model` and `vehicle_class` at the top level of the JSON schema, the producer threw a `409 Conflict` error from the Schema Registry, even after updating the local schema string.

### Cause
The Schema Registry's default `BACKWARD` compatibility mode prevents adding new properties to an "open content model" (standard JSON object) because existing consumers using older schema versions wouldn't know how to handle the new fields. This is considered a breaking change.

### Resolution
1. **Manual Registry Update**: The schema was manually updated in the Confluent Cloud Console to Version 3, effectively forcing the registry to accept the new structure.
2. **Schema Alignment**: The local `schema_str` in `simulator/producer.py` was updated to match Version 3 exactly.
3. **Bypass Strategy**: During the transition, schema validation was temporarily bypassed using `json.dumps()` to verify data flow before restoring the strict `JSONSerializer`.

---

## 7. "Impossible" AUC-ROC Score (0.9998) due to Label Leakage

### Issue
Retraining the XGBoost model on the newly generated gold layer data resulted in an AUC-ROC score of 0.9998. While mathematically impressive, this is unrealistically high for a predictive maintenance task and indicates a failure in the machine learning design.

### Cause
**Label Leakage**: The target variable (`is_at_risk`) was derived directly from the `health_score` calculated in the Gold layer SQL. The features used for training (`avg_coolant_temp`, `avg_battery_voltage`, etc.) were the exact same variables used in the SQL logic to determine that health score. XGBoost effectively reverse-engineered the SQL thresholds (e.g., "if temp > 108 then health drops") rather than learning latent mechanical risk patterns.

### Resolution
1. **Break the direct link**: Remove the "cheating" features (simple averages used in SQL) from the training set.
2. **Introduce Environmental Noise**: Add variables like `ambient_temperature` to the simulator. This forces the model to distinguish between weather-related heat (normal) and engine-related heat (anomalous) without knowing the weather state.
3. **Shift to Complex Signals**: Use features that require interpretation, such as rate-of-change (`max_coolant_temp_delta`) and efficiency ratios (`maf / rpm`), which are correlated with health but not directly used in the linear scoring formula.
