# Testing

## Run tests

```bash
pytest tests/ -v
pytest tests/ -v --cov=src/ldc --cov-report=term-missing
```

## Structure

```
tests/
├── domain/
│   └── test_graph.py          # DependencyGraph, topological sort, cycle detection
└── application/
    ├── test_env_resolver.py   # .env parsing, merge order
    └── test_check_command.py  # CheckCommand with mock checker/reporter
```

## Writing tests for commands

Commands take ports via constructor injection — pass mock implementations:

```python
from unittest.mock import MagicMock
from ldc.application.commands.check import CheckCommand
from ldc.domain.models import PrerequisiteReport, CheckResult

checker = MagicMock()
checker.check.return_value = PrerequisiteReport(
    service_name="my-svc",
    checks=[CheckResult("java runtime", True, "java 17.0.0")],
)
reporter = MagicMock()

cmd = CheckCommand(checker, reporter)
result = cmd.execute(config)
assert result is True
```

No subprocesses, no filesystem, no network — just domain objects.

## Testing the domain

Domain classes have no external dependencies. Test them directly:

```python
from ldc.domain.graph import DependencyGraph
from ldc.domain.exceptions import CircularDependencyError

g = DependencyGraph({"a": ["b"], "b": ["c"], "c": []})
assert g.startup_order(["a"]) == ["c", "b", "a"]
```

## What not to unit-test

Adapters (`WindowsProcessRunner`, `SubprocessGitClient`, etc.) require the
real OS. Test them manually or with integration tests against a real environment.
The port interfaces make it straightforward to mock them out everywhere else.
