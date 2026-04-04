# Health Checks

ldc polls a health check after starting each service and blocks until healthy
or the timeout is exceeded.

## Types

### http

```yaml
health_check:
  type: http
  url: http://localhost:8080/actuator/health
  timeout: 60
  interval: 5
```

GET request via `urllib`. Response `2xx` = healthy. No auth support — use a
public health endpoint.

### tcp

```yaml
health_check:
  type: tcp
  host: localhost
  port: 5432
  timeout: 30
  interval: 3
```

`socket.create_connection()` with a 3-second connect timeout. Use for databases,
message brokers, or any service without an HTTP health endpoint.

### command

```yaml
health_check:
  type: command
  command: "pg_isready -h localhost -p 5432"
  expected_output: "accepting connections"   # optional substring match
  timeout: 30
  interval: 5
```

Exit code `0` = healthy. `expected_output` requires the substring to appear in
stdout+stderr.

### process

```yaml
health_check:
  type: process
  timeout: 10
```

Passes as soon as the process is alive. Use for services with no network
endpoint or as a quick smoke-test.

## Common fields

| field | default | description |
|-------|---------|-------------|
| `timeout` | `60` | total seconds to wait |
| `interval` | `5` | seconds between polls |
| `retries` | `12` | max poll attempts |

ldc stops polling at `timeout` seconds regardless of `retries`.

## No health check

If `health_check` is omitted, ldc waits 1 second and marks the service
healthy if the process is still alive. Fine for fast-starting services during
development; add a proper check for anything shared by teammates.
