# Infrastructure

The project uses ClickHouse for storing and analyzing vehicle telemetry data.

## ClickHouse (Container)

For development, a ClickHouse server is managed via `podman-compose`. Connection details are configured in the `.env` file.

- **Host**: `CLICKHOUSE_HOST` (default: localhost)
- **Port**: `CLICKHOUSE_PORT` (default: 8124)
- **User**: `CLICKHOUSE_USER` (default: admin)
- **Password**: `CLICKHOUSE_PASSWORD`
- **Database**: `CLICKHOUSE_DATABASE` (default: canflow)

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
