# Configuration Reference

All configuration lives in `composer.yml` (default) or any file passed via `-f`.

See [`composer.example.yml`](../composer.example.yml) for a full working example.

---

## Top-level structure

```yaml
workspace:
  root: ./services      # where repos are cloned
  log_dir: ./logs       # per-service log files
  workers: 4            # max parallel threads for clone / install / up (default: 4)

services:
  <name>: ...           # service definitions

groups:
  <name>: ...           # named service sets
```

---

## Service fields

```yaml
services:
  my-service:
    # Source control
    repo: https://github.com/org/my-service.git
    branch: main                  # default: main
    dir: ./services/my-service    # optional override for clone path

    # Runtime: java | python | node | dotnet | external | custom
    runtime: java
    description: "Human-readable label"

    # Dependencies — started before this service
    depends_on:
      - postgres
      - config-server

    # Environment variables (isolated per service)
    env:
      SERVER_PORT: "8080"
      DATABASE_URL: jdbc:postgresql://localhost:5432/mydb
    env_files:                    # merged in order; last wins; secrets go here
      - .env.base
      - .env.my-service

    # Host prerequisites
    requires:
      java: ">=17"
      python: ">=3.9"
      node: ">=18"
      dotnet: ">=6"
      commands: [mvn, curl]       # must be on PATH
      env_vars: [JAVA_HOME]       # must be set
      folders:                    # created automatically with --fix
        - C:/data/my-service
      files:
        - C:/config/secret.properties
      ports_free: [8080]          # checked before start

    # Install step (run once, or on demand)
    install:
      command: mvn clean package -DskipTests -q
      working_dir: .              # relative to service dir

    # Start command
    start:
      command: java -jar target/my-service.jar
      args: ["--spring.config.location=./config/"]
      working_dir: .

    # Health check
    health_check:
      type: http                  # http | tcp | command | process
      url: http://localhost:8080/actuator/health
      timeout: 60                 # seconds to wait for healthy
      interval: 5                 # poll interval
      retries: 12

    labels:
      team: platform
      tier: backend
```

---

## Variable expansion

`${VAR}` syntax is supported in both `env_files` and inline `env:` values.
Variables are expanded against: system environment → values from earlier env_files → values already defined in the same file.
Unresolved references are left as-is.

```yaml
# .env.base
DB_HOST=localhost

# composer.yml
services:
  my-service:
    env_files:
      - .env.base
    env:
      DB_URL: jdbc:postgresql://${DB_HOST}/mydb   # expanded from .env.base
```

---

## Health check types

| type | required fields | description |
|------|----------------|-------------|
| `http` | `url` | GET request; 2xx = healthy |
| `tcp` | `host`, `port` | TCP connect |
| `command` | `command`, (opt) `expected_output` | exit 0 = healthy |
| `process` | — | process is alive |

---

## External services

Use `runtime: external` for local infrastructure (databases, brokers) that ldc
should wait on but not clone or manage:

```yaml
postgres:
  runtime: external
  health_check:
    type: tcp
    host: localhost
    port: 5432
    timeout: 30
  start:
    command: "net start postgresql-x64-14"   # optional — run to start it
```

---

## Groups

```yaml
groups:
  gateway-dev:
    description: "Minimum deps for gateway development"
    services:
      - postgres
      - config-server
      - gateway
```

Used with: `ldc up --group gateway-dev`
