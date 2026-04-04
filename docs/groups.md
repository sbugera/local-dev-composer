# Groups

Groups are named sets of services for quick selection. They solve the "magic
button" problem: declare the minimum set you need per development scenario,
and ldc automatically includes all transitive dependencies.

## Define a group

```yaml
groups:
  gateway-dev:
    description: "Minimum deps to develop the gateway"
    services:
      - postgres
      - config-server
      - gateway

  user-dev:
    description: "Minimum deps for user-service"
    services:
      - postgres
      - config-server
      - user-service

  full-stack:
    description: "Everything"
    services:
      - postgres
      - config-server
      - gateway
      - user-service
      - notification-service
```

## Use a group

```bash
ldc up --group gateway-dev
ldc up -g user-dev
```

ldc resolves transitive dependencies for every service in the group. If
`gateway` depends on `config-server` which depends on nothing, the startup
order is: `postgres` → `config-server` → `gateway`.

## Listing groups

Groups are defined in your `composer.yml`. Use `ldc doctor` to see which
services are configured and their status.

## Recommended pattern

Create one group per developer scenario, not per team or tier:

```yaml
groups:
  working-on-payments:
    services: [postgres, config-server, user-service, payment-service]

  working-on-notifications:
    services: [postgres, rabbitmq, notification-service]
```

Services not in the group are never started — this is the "smart mapping"
that keeps local resource usage minimal.
