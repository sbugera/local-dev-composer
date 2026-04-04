# Architecture

ldc uses **Hexagonal Architecture** (Ports & Adapters). The domain is pure
Python with no I/O; all external interactions are behind abstract interfaces.

## Layer map

```
src/ldc/
├── domain/          Pure logic — zero I/O, zero external deps
├── ports/           Abstract interfaces (ABCs) the app depends on
├── adapters/        Concrete implementations injected at startup
└── application/     Use cases + DI container
```

## Domain layer

`domain/models.py` — all dataclasses:

| class | purpose |
|-------|---------|
| `WorkspaceConfig` | full parsed config |
| `Service` | one service definition |
| `ServiceState` | runtime state (pid, status, log) |
| `Prerequisites` | what must be true on the host |
| `HealthCheckConfig` | how to probe health |
| `PrerequisiteReport` | check results with fix hints |

`domain/graph.py` — `DependencyGraph`:

```python
graph = DependencyGraph.from_services(config.services)
order = graph.startup_order(["gateway"])   # topological sort
```

Kahn's algorithm. Raises `CircularDependencyError` immediately on cycles.

## Ports (interfaces)

| port | implementors |
|------|-------------|
| `IConfigReader` | `YamlConfigReader` |
| `IProcessRunner` | `WindowsProcessRunner` |
| `IHealthChecker` | `CompositeHealthChecker` → Http/Tcp/Command |
| `IGitClient` | `SubprocessGitClient` |
| `IPrerequisiteChecker` | `SystemPrerequisiteChecker` |
| `IReporter` | `RichReporter` |
| `IInstaller` | `SubprocessInstaller` |
| `IStateStore` | `JsonStateStore` |

## Adapters

### WindowsProcessRunner (`adapters/process/windows_runner.py`)

- Spawns with `CREATE_NEW_PROCESS_GROUP` for clean shutdown
- Stdout/stderr redirected to `<log_dir>/<service>.log`
- Tracks PIDs via `IStateStore`; `psutil` for alive checks and tree termination

### JsonStateStore (`adapters/state/json_store.py`)

Writes `.ldc/state.json` after every state change. On next `ldc` invocation,
loads existing PIDs and reconciles (marks dead processes STOPPED).

### RichReporter (`adapters/reporting/rich_reporter.py`)

- Live dashboard: `rich.Live` + daemon thread polling at 500ms
- Falls back to plain ASCII if `rich` is not installed
- All IReporter methods are no-op safe

### CompositeHealthChecker (`adapters/health/composite_checker.py`)

Delegates to the first registered checker whose `supports()` returns True:

```python
CompositeHealthChecker([
    HttpHealthChecker(),
    TcpHealthChecker(),
    CommandHealthChecker(),
])
```

## Application layer

### container.py — DI wiring

Single place to swap adapters:

```python
class Container:
    def __init__(self, ldc_dir: Path = Path(".ldc")) -> None:
        self.reporter = RichReporter()
        self.runner = WindowsProcessRunner(self.state_store)
        self.up_cmd = UpCommand(self.runner, self.health_checker, ...)
```

### Use case commands

Each command takes only the ports it needs via constructor injection. Fully
unit-testable by passing mock implementations.

```python
cmd = CheckCommand(checker=MockChecker(), reporter=MockReporter())
result = cmd.execute(config, service_names=["gateway"])
```

## Adding a new adapter

To swap out any adapter (e.g. replace `RichReporter` with a JSON reporter):

1. Implement the relevant port ABC
2. Replace the instance in `container.py`
3. No other code changes required

## Adding a new command

1. Create `src/ldc/application/commands/my_cmd.py`
2. Inject ports via `__init__`
3. Add to `container.py`
4. Add argparse subcommand in `src/ldc/cli.py`
5. Update `docs/commands.md`
