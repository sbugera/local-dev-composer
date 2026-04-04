# Per-Service Environment Isolation

Each service process gets its own environment dictionary built at startup.
The same variable name can hold different values for different services.

## Merge order (later wins)

```
1. Inherited system environment  (os.environ)
2. env_file entries               (.env.my-service)
3. Inline env block               (composer.yml service.env)
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

```bash
# .env.gateway
DB_PASSWORD=secret123
OAUTH_CLIENT_SECRET=abc
```

```yaml
# composer.yml
services:
  gateway:
    env_file: .env.gateway
    env:
      DATABASE_URL: jdbc:postgresql://localhost:5432/gateway_db
```

The inline `env` block wins over `env_file` if the same key appears in both.

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
