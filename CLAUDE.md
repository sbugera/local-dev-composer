# local-dev-composer (ldc)

Windows-native CLI tool to orchestrate local microservice development environments
without Docker, Podman, or WSL.

## Architecture: Hexagonal (Ports & Adapters)

```
src/ldc/
├── domain/          Pure business logic — no I/O, no external libs
│   ├── models.py    All domain dataclasses (Service, WorkspaceConfig, ServiceState, …)
│   ├── graph.py     Dependency graph + topological sort (startup/shutdown ordering)
│   └── exceptions.py Domain-level exceptions
│
├── ports/           Abstract interfaces (ABCs) the application depends on
│   ├── config_reader.py       IConfigReader
│   ├── process_runner.py      IProcessRunner
│   ├── health_checker.py      IHealthChecker
│   ├── git_client.py          IGitClient
│   ├── prerequisite_checker.py IPrerequisiteChecker
│   ├── reporter.py            IReporter
│   ├── installer.py           IInstaller
│   └── state_store.py         IStateStore
│
├── adapters/        Concrete implementations wired at startup
│   ├── config/yaml_reader.py          YAML → WorkspaceConfig
│   ├── process/windows_runner.py      subprocess + psutil process manager
│   ├── health/http_checker.py         urllib HTTP health check
│   ├── health/tcp_checker.py          socket TCP health check
│   ├── health/command_checker.py      shell command health check
│   ├── health/composite_checker.py    Dispatches to correct checker by type
│   ├── git/subprocess_client.py       System git via subprocess
│   ├── prerequisites/system_checker.py Java/Python/Node/cmd/env/folder/port checks
│   ├── reporting/rich_reporter.py     Rich TUI dashboard + tables
│   └── state/json_store.py            .ldc/state.json persistence
│
└── application/     Use cases — coordinate domain + ports
    ├── container.py             DI wiring (one place to swap adapters)
    ├── env_resolver.py          Per-service env merge (system + .env file + inline)
    ├── installer_service.py     SubprocessInstaller
    └── commands/
        ├── clone.py    CloneCommand
        ├── check.py    CheckCommand
        ├── install.py  InstallCommand
        ├── up.py       UpCommand    ← main orchestration
        ├── down.py     DownCommand
        ├── status.py   StatusCommand
        ├── logs.py     LogsCommand
        └── doctor.py   DoctorCommand
```

## Key design decisions

- **Per-service environment isolation**: each service subprocess gets its own `env`
  dict built by `env_resolver.py` — same variable name can hold different values
  for different services. Merge order: system env → .env file → inline yaml env.

- **Dependency ordering**: `DependencyGraph` uses Kahn's algorithm (topological sort).
  `up` starts leaf dependencies first; `down` stops in reverse. Circular deps raise
  `CircularDependencyError` immediately.

- **No Docker/WSL**: processes run as native Windows subprocesses with
  `CREATE_NEW_PROCESS_GROUP` for clean shutdown. `psutil` used for PID tracking
  and graceful termination (terminate children first, then parent, then force-kill).

- **State persistence**: `.ldc/state.json` stores PIDs across sessions so `ldc` can
  detect already-running processes on restart and avoid double-starting.

- **Rich TUI**: `rich` is optional — if not installed, all output falls back to plain
  ASCII. The live dashboard polls every 500ms from a daemon thread.

- **Groups**: named sets of services for quick selection. `ldc up --group gateway-dev`
  starts only the minimum required services including transitive dependencies.

## CLI entry point

`ldc.py` at the repo root — adds `src/` to `sys.path` and routes argparse subcommands
to command objects from `container.py`.

## Running

```bash
# Install dependencies
pip install -e ".[dev]"

# Or without editable install
pip install rich pyyaml psutil

# Run directly
python ldc.py up --group gateway-dev
python ldc.py doctor
python ldc.py logs gateway -f
```

## Documentation

```
docs/
├── installation.md      Setup, Nexus proxy, direct-script mode
├── configuration.md     Full composer.yml schema reference
├── commands.md          All CLI commands with options and examples
├── groups.md            Named service sets, smart selection
├── environment.md       Per-service env isolation, .env files, merge order
├── prerequisites.md     Runtime/command/folder/port checks
├── health-checks.md     HTTP, TCP, command, process health check types
├── state-and-logs.md    .ldc/state.json, log files, clearing state
├── architecture.md      Hexagonal design, layers, how to extend
└── testing.md           Running tests, writing new ones
```

**Keep docs in sync with code.** After any change that affects user-facing behaviour:

- New command → add to `docs/commands.md`
- New health check type → add to `docs/health-checks.md`
- New prerequisite check → add to `docs/prerequisites.md`
- New config field → add to `docs/configuration.md`
- New adapter or port → update `docs/architecture.md`
- Architecture change → update both `docs/architecture.md` and `CLAUDE.md`
- `README.md` links to every doc file — update the table if files are added or renamed

Docs are concise and technical: code snippets first, prose only where necessary.

---

## Adding a new health check type

1. Create `src/ldc/adapters/health/my_checker.py` implementing `IHealthChecker`
2. Register it in `container.py` inside `CompositeHealthChecker([...])`
3. Add the new type to `HealthCheckType` enum in `domain/models.py`
4. Handle it in `adapters/config/yaml_reader.py`

## Adding a new command

1. Create `src/ldc/application/commands/my_cmd.py` with a class `MyCommand`
2. Wire it in `container.py`
3. Add the argparse subcommand in `ldc.py`

## Testing

```bash
pytest tests/ -v
```

Domain and application layers are unit-testable in isolation — inject mock adapters
via constructor injection in `Container` or by instantiating commands directly.
