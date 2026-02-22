# Infrastructure

The project uses ClickHouse for storing and analyzing vehicle telemetry data.

## ClickHouse (Container)

For development, a ClickHouse server is managed via `podman-compose`.

- **Host Port**: 8124 (maps to container 8123)
- **Native Port**: 9001 (maps to container 9000)
- **User**: admin
- **Password**: password
- **Volume**: `./data/clickhouse` (ignored by git)

### Management

Start the service:
```bash
podman-compose up -d
```

Stop the service:
```bash
podman-compose down
```

## Existing Services

Note: Port 8123 is reserved for a native ClickHouse installation on this system.
