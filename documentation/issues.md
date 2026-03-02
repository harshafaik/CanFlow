# Known Issues & Troubleshooting

This document tracks technical hurdles encountered during the development of CanFlow and their respective resolutions.

---

## 🛰️ Kafka & Schema Registry

### 1. Confluent Schema Registry Incompatibility
!!! danger "Issue: 409 Conflict"
    When updating the `VehicleProducer` to include schema validation, a `409 Conflict` error was returned by Confluent Cloud.
    ```text
    Error producing message: Schema being registered is incompatible with an earlier schema for subject "vehicle.telemetry.raw-value"
    ```

??? info "Root Cause"
    The initial auto-generated schema in Confluent Cloud did not define any fields as `required`. The updated local schema explicitly added a `required: [...]` array. Under `BACKWARD` compatibility rules (the default), adding a required field is considered a breaking change because old producers would produce invalid data according to the new schema.

!!! success "Resolution"
    The local JSON schema string was modified to remove the `required` constraints, matching the loose structure of the Version 1 schema already residing in the Registry.

### 2. JSONDeserializer Strict Constructor Signature
!!! danger "Issue: ValueError"
    The `confluent-kafka` Python library's `JSONDeserializer` threw multiple `TypeError` and `ValueError` during initialization.
    ```text
    ValueError: from_dict must be callable with the signature from_dict(dict, SerializationContext) -> object
    ```

??? info "Root Cause"
    The `JSONDeserializer` constructor is highly sensitive to positional arguments and the signature of the `from_dict` hook:
    1. It expects a callable for `from_dict` that accepts exactly two arguments: the dictionary and the `SerializationContext`.
    2. Passing the `SchemaRegistryClient` as a positional argument was causing it to be misinterpreted as the `from_dict` hook.

!!! success "Resolution"
    1. Defined an explicit helper function `dict_to_telemetry(obj, ctx)` to satisfy the two-argument requirement.
    2. Used **explicit keyword arguments** during initialization to ensure parameters were mapped correctly.

---

## 🗄️ Database & Ingestion

### 3. Bronze Table Schema Mismatch
!!! danger "Issue: Unrecognized Column"
    The stream consumer failed to flush data to ClickHouse with the following error:
    ```text
    ERROR:writer:Failed to flush to ClickHouse: Unrecognized column 'anomaly_reason' in table bronze_telemetry
    ```

??? info "Root Cause"
    The `bronze_telemetry` table was previously created with an older schema that did not include the `anomaly_reason` field. Since the `stream/transforms.py` pipeline was now producing this field, the ClickHouse `INSERT` statement failed because the table structure was outdated.

!!! success "Resolution"
    The `bronze_telemetry` table was manually dropped. Upon the next run of the `stream/consumer.py`, the `ClickHouseWriter` automatically recreated the table using the up-to-date schema defined in its `_ensure_table` method.

### 4. ClickHouseWriter Threading Deadlock
!!! danger "Issue: Ingestion Hang"
    The `stream/consumer.py` would connect to Kafka and receive messages, but data would never appear in ClickHouse. The process appeared to hang indefinitely after reaching the buffer threshold.

??? info "Root Cause"
    In `stream/writer.py`, the `add()` method acquired a standard `threading.Lock()` and then called `self.flush()`. The `flush()` method also attempted to acquire the same lock. Since `threading.Lock` is non-reentrant, the thread deadlocked itself.

!!! success "Resolution"
    The lock type was changed from `threading.Lock()` to `threading.RLock()` (Re-entrant Lock). This allows the same thread to acquire the lock multiple times.

---

## 📈 Machine Learning & Analytics

### 5. "Impossible" AUC-ROC Score (0.9998)
!!! danger "Issue: Label Leakage"
    Retraining the XGBoost model on the newly generated gold layer data resulted in an AUC-ROC score of 0.9998, which is unrealistically high for predictive maintenance.

??? info "Root Cause"
    **Label Leakage**: The target variable (`is_at_risk`) was derived directly from the `health_score` calculated in SQL. The features used for training were the exact same variables used in the SQL logic. XGBoost effectively reverse-engineered the SQL thresholds rather than learning latent mechanical patterns.

!!! success "Resolution"
    1. **Break the direct link**: Removed the "cheating" features from the training set.
    2. **Introduce Environmental Noise**: Added variables like `ambient_temperature` to the simulator.
    3. **Shift to Complex Signals**: Used features that require interpretation, such as rate-of-change (`max_coolant_temp_delta`) and efficiency ratios (`maf / rpm`).

---

## 📊 Dashboard & Visualization

### 6. Dashboard Time-Drift (UTC vs. Local Time)
!!! danger "Issue: Empty Panels"
    After setting up the Grafana dashboard, all "Last 1 hour" panels appeared empty even though the simulator and consumer were running.

??? info "Root Cause"
    **Timestamp Mismatch**: The simulator was using local system time, while ClickHouse and Grafana default to UTC. This created a 5.5-hour gap, making live data appear to Grafana as being in the future.

!!! success "Resolution"
    The simulator's `format_telemetry` method was updated to use explicit UTC timestamps using `datetime.now(timezone.utc).isoformat()`.

### 7. Grafana ClickHouse DataSource: "Invalid Server Host"
!!! danger "Issue: 400 Connection Error"
    Grafana failed to connect to ClickHouse with a 400 error: `invalid server host. Either empty or not set`.

??? info "Root Cause"
    While the `url` field was provided in the provisioning YAML, the `grafana-clickhouse-datasource` plugin requires the `server` and `port` fields to be explicitly defined within the `jsonData` block.

!!! success "Resolution"
    The `clickhouse.yml` provisioning file was updated to include both the top-level URL and the explicit `jsonData` fields (`server`, `port`, `protocol`).
