# local-dev-composer (ldc)

Orchestrate local microservice environments on **Windows 11** without Docker, Podman, or WSL.

- Start a full service graph with one command
- Per-service environment isolation (same variable, different values per service)
- Dependency ordering — services start leaf-first, stop dependents-first
- Prerequisite checks with actionable fix hints (Java version, PATH commands, env vars, ports, folders)
- Live Rich terminal dashboard
- Groups — declare the minimum set of services per development scenario
- Survives restarts — reconciles live PIDs from `.ldc/state.json`

## Quick start

```bash
git clone https://github.com/sbugera/local-dev-composer.git
cd local-dev-composer
pip install -e .

cp composer.example.yml composer.yml
# edit composer.yml for your project

ldc doctor                     # check everything, get a numbered fix list
ldc clone                      # clone all repos
ldc check --fix                # verify and fix prerequisites
ldc install                    # run install commands
ldc up --group gateway-dev     # start minimum services for your task
```

## Daily use

```bash
ldc up --group gateway-dev     # start what you need
ldc status                     # service table with PIDs and health
ldc logs gateway -f            # follow a service log
ldc down                       # stop everything
```

## Documentation

| topic | description |
|-------|-------------|
| [Installation](docs/installation.md) | Setup, Nexus proxy, direct-script mode |
| [Configuration](docs/configuration.md) | Full `composer.yml` schema reference |
| [Commands](docs/commands.md) | All CLI commands with options |
| [Groups](docs/groups.md) | Named service sets, smart selection |
| [Environment](docs/environment.md) | Per-service env isolation, `.env` files |
| [Prerequisites](docs/prerequisites.md) | Runtime/command/folder/port checks |
| [Health Checks](docs/health-checks.md) | HTTP, TCP, command, process types |
| [State & Logs](docs/state-and-logs.md) | `.ldc/state.json`, log files, clearing state |
| [Architecture](docs/architecture.md) | Hexagonal design, layers, extending ldc |
| [Testing](docs/testing.md) | Running tests, writing new ones |

## Requirements

- Python 3.9+
- Git for Windows
- Windows 11
- No Docker, no WSL
