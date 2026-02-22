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
