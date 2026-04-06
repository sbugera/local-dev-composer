# local-dev-composer (ldc)

Orchestrate local microservice environments on Windows without Docker, Podman, or WSL.

- Start a full service graph with one command
- Per-service environment isolation (same variable, different values per service)
- Dependency ordering — services start leaf-first, stop dependents-first
- Prerequisite checks with actionable fix hints (Java version, PATH commands, env vars, ports, folders)
- Live Rich terminal dashboard
- Groups — declare the minimum set of services per development scenario
- Survives restarts — reconciles live PIDs from `.ldc/state.json`

## Install

```bash
pip install local-dev-composer
```

## Quick start

> If `ldc` is not recognised after install, see [Installation](https://github.com/sbugera/local-dev-composer/blob/master/docs/installation.md) for PATH setup options.

```bash
# Download the example config and adapt it to your project
curl -O https://raw.githubusercontent.com/sbugera/local-dev-composer/master/composer.example.yml
cp composer.example.yml composer.yml
# edit composer.yml

ldc bootstrap                  # clone + install + start everything in one shot
```

Or step by step:

```bash
ldc doctor                     # check everything, get a numbered fix list
ldc clone                      # clone all repos
ldc check --fix                # verify and fix prerequisites
ldc install                    # run install commands
ldc up --group gateway-dev     # start minimum services for your task
```

## Daily use

```bash
ldc up --group gateway-dev     # start what you need
ldc rebuild backend            # stop + reinstall + start after code changes
ldc restart gateway            # stop + start (no reinstall)
ldc status                     # service table with PIDs and health
ldc logs gateway -f            # follow a service log
ldc down                       # stop everything
```

## Requirements

- Python 3.9+
- Git for Windows
- Windows
- No Docker, no WSL

## Documentation

Full documentation is available on [GitHub](https://github.com/sbugera/local-dev-composer):

- [Installation](https://github.com/sbugera/local-dev-composer/blob/master/docs/installation.md)
- [Configuration](https://github.com/sbugera/local-dev-composer/blob/master/docs/configuration.md)
- [Commands](https://github.com/sbugera/local-dev-composer/blob/master/docs/commands.md)
- [Groups](https://github.com/sbugera/local-dev-composer/blob/master/docs/groups.md)
- [Environment variables](https://github.com/sbugera/local-dev-composer/blob/master/docs/environment.md)
- [Prerequisites](https://github.com/sbugera/local-dev-composer/blob/master/docs/prerequisites.md)
- [Health checks](https://github.com/sbugera/local-dev-composer/blob/master/docs/health-checks.md)
- [State & logs](https://github.com/sbugera/local-dev-composer/blob/master/docs/state-and-logs.md)
- [Architecture](https://github.com/sbugera/local-dev-composer/blob/master/docs/architecture.md)
- [Testing](https://github.com/sbugera/local-dev-composer/blob/master/docs/testing.md)

## Source & contributing

[https://github.com/sbugera/local-dev-composer](https://github.com/sbugera/local-dev-composer)
