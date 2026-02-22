# Performance Metrics

This document tracks the performance characteristics of the CanFlow ingestion pipeline observed during stress testing.

## Stress Test: 100k+ Rows (2026-02-22)

During a high-throughput run to verify system stability and reach initial data targets, the following performance was observed.

### System Configuration
- **Simulation Agents**: 20 independent `VehicleAgent` instances.
- **Emission Rate**: 0.1 seconds (10Hz) per agent.
- **Total Throughput**: ~200 events per second (EPS).
- **Kafka Strategy**: Serialized JSON with Schema Registry validation.
- **ClickHouse Strategy**: Buffered writes (100 rows threshold or 5s interval).

### Observed Metrics
- **Total Ingested Rows**: 116,500
- **Duration**: ~60 seconds of active generation + tail-end ingestion.
- **Ingestion Rate**: Verified at ~1,940 rows per second average (including parallel processing and buffering).
- **Stability**: Post-deadlock fix (using `RLock`), the system handled 100k+ rows without memory leaks or buffer overflows.

### Bottleneck Analysis
- **CPU**: Minimal impact on agent side; Python's `confluent-kafka` client is highly efficient (librdkafka based).
- **Network**: Confluent Cloud handled ~200 EPS with negligible latency.
- **Storage**: ClickHouse MergeTree storage handled the 100 row batch inserts without any "Too many parts" warnings.

## Optimal Configuration for Development
Based on these tests, the default development configuration is set to:
- `NUM_VEHICLES=5`
- `EMIT_INTERVAL_SECONDS=1`
This provides a steady, readable stream of ~5 EPS for testing dashboard and anomaly logic without unnecessary resource consumption.
