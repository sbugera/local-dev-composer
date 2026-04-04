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
      - .env.base           # shared defaults (e.g. NEXUS_URL, LOG_LEVEL)
      - .env.gateway        # service-specific secrets; overrides .env.base
    env:
      DATABASE_URL: jdbc:postgresql://localhost:5432/gateway_db
```

```bash
# .env.base
LOG_LEVEL=INFO
NEXUS_URL=https://nexus.company.com

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
```

## System env passthrough

System environment variables are inherited by all services unless overridden.
This means `PATH`, `JAVA_HOME`, `USERPROFILE`, proxy settings, etc. are
available to all service processes without repeating them in config.
