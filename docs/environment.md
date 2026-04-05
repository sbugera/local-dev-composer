# Per-Service Environment Isolation

Each service process gets its own environment dictionary built at startup.
The same variable name can hold different values for different services.

## Merge order (later wins)

```
1. Inherited system environment  (os.environ)
2. env_files[0]                   first file
3. env_files[1]                   second file (overrides first)
   ...
4. Inline env block               (composer.yml service.env) — always wins
```

## Example

Two services share the variable name `DATABASE_URL` with different values:

```yaml
services:
  gateway:
    env:
      DATABASE_URL: jdbc:postgresql://localhost:5432/gateway_db
      SERVER_PORT: "8080"

  user-service:
    env:
      DATABASE_URL: postgresql://localhost:5432/users_db
      SERVER_PORT: "8001"
```

Each process receives only its own `DATABASE_URL`. Neither sees the other's.

## .env files

Secrets and machine-specific values belong in `.env` files, not in `composer.yml`.

```yaml
# composer.yml
services:
  gateway:
    env_files:
      - .env.base           # shared defaults (e.g. LOG_LEVEL)
      - .env.gateway        # service-specific secrets; overrides .env.base
    env:
      DATABASE_URL: jdbc:postgresql://localhost:5432/gateway_db
```

```bash
# .env.base
LOG_LEVEL=INFO

# .env.gateway
DB_PASSWORD=secret123
LOG_LEVEL=DEBUG        # overrides .env.base
```

Single file is also accepted:

```yaml
env_files:
  - .env.gateway

# or legacy single-value form (still supported):
env_file: .env.gateway
```

The inline `env` block always wins over any file.

## .env file syntax

```bash
KEY=value
KEY="value with spaces"
KEY='single quoted'
export KEY=value     # export prefix is stripped
# comments ignored
KEY2=${KEY}/suffix   # variable expansion supported
```

## Variable expansion

`${VAR}` is expanded in both `.env` files and inline `env:` values.
Expansion context: system env + values from earlier env_files + values already parsed in the same file (top to bottom).
Unresolved references are kept as-is.

```bash
# .env.base
DB_HOST=localhost

# .env.my-service
DB_URL=jdbc:postgresql://${DB_HOST}/mydb   # expands using .env.base
```

```yaml
# composer.yml — inline env: also supports expansion
env:
  DB_URL: jdbc:postgresql://${DB_HOST}/mydb   # expanded from system env or env_files
```

## System env passthrough

System environment variables are inherited by all services unless overridden.
This means `PATH`, `JAVA_HOME`, `USERPROFILE`, proxy settings, etc. are
available to all service processes without repeating them in config.

## Python virtual environments

Put venv creation and activation directly in the `install` and `start` commands:

```yaml
services:
  user-service:
    runtime: python
    install:
      command: "python -m venv .venv && call .venv\\Scripts\\activate.bat && pip install -r requirements.txt"
    start:
      command: "call .venv\\Scripts\\activate.bat && python -m uvicorn app.main:app --port 8001"
```

`call` is required on Windows to source the activate batch script so the subsequent command inherits the venv environment. On Linux/macOS use `source .venv/bin/activate` instead.

