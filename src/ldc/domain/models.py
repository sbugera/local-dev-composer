"""
Core domain models — pure Python, zero external dependencies.
These represent the fundamental concepts of the orchestration domain.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ServiceStatus(Enum):
    PENDING = "pending"
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"
    FAILED = "failed"
    SKIPPED = "skipped"
    INSTALLING = "installing"
    CLONING = "cloning"


class Runtime(Enum):
    JAVA = "java"
    PYTHON = "python"
    NODE = "node"
    DOTNET = "dotnet"
    EXTERNAL = "external"   # Local dependency (DB, message broker) — not cloned
    CUSTOM = "custom"


class HealthCheckType(Enum):
    HTTP = "http"
    TCP = "tcp"
    COMMAND = "command"
    PROCESS = "process"     # Just verify the process is alive


# ---------------------------------------------------------------------------
# Configuration sub-models
# ---------------------------------------------------------------------------

@dataclass
class HealthCheckConfig:
    type: HealthCheckType
    url: Optional[str] = None           # HTTP
    host: Optional[str] = "localhost"   # TCP
    port: Optional[int] = None          # TCP
    command: Optional[str] = None       # COMMAND
    expected_output: Optional[str] = None  # COMMAND — substring to match
    interval_seconds: int = 5
    timeout_seconds: int = 60
    retries: int = 12


@dataclass
class Prerequisites:
    """What must be true on the host before this service can run."""
    java: Optional[str] = None          # e.g. ">=17"
    python: Optional[str] = None        # e.g. ">=3.9"
    node: Optional[str] = None          # e.g. ">=18"
    dotnet: Optional[str] = None        # e.g. ">=6"
    commands: List[str] = field(default_factory=list)   # binaries that must be on PATH
    env_vars: List[str] = field(default_factory=list)   # env vars that must exist
    folders: List[str] = field(default_factory=list)    # folders (auto-created if absent)
    files: List[str] = field(default_factory=list)      # files that must exist
    ports_free: List[int] = field(default_factory=list) # ports that must be unbound


@dataclass
class InstallConfig:
    command: str
    working_dir: str = "."


@dataclass
class StartConfig:
    command: str
    args: List[str] = field(default_factory=list)
    working_dir: str = "."


# ---------------------------------------------------------------------------
# Top-level domain objects
# ---------------------------------------------------------------------------

@dataclass
class Service:
    name: str
    runtime: Runtime
    depends_on: List[str] = field(default_factory=list)

    # Source control
    repo: Optional[str] = None
    branch: str = "main"
    dir: Optional[str] = None          # override default clone dir under workspace.root

    # Environment
    env: Dict[str, str] = field(default_factory=dict)
    env_files: List[str] = field(default_factory=list)  # merged in order; last wins

    # Lifecycle
    requires: Optional[Prerequisites] = None
    install: Optional[InstallConfig] = None
    start: Optional[StartConfig] = None
    health_check: Optional[HealthCheckConfig] = None

    # Metadata
    labels: Dict[str, str] = field(default_factory=dict)
    description: str = ""


@dataclass
class Group:
    """A named set of services for quick selection."""
    name: str
    description: str
    services: List[str]


@dataclass
class WorkspaceConfig:
    root: str                                   # where repos are cloned
    services: Dict[str, Service]
    groups: Dict[str, Group] = field(default_factory=dict)
    log_dir: str = "./logs"
    workers: int = 4                            # max parallel threads (clone/install/up)


# ---------------------------------------------------------------------------
# Runtime state (transient, not persisted in config)
# ---------------------------------------------------------------------------

@dataclass
class ServiceState:
    name: str
    status: ServiceStatus = ServiceStatus.PENDING
    pid: Optional[int] = None
    started_at: Optional[str] = None
    last_health_check_at: Optional[str] = None
    last_error: Optional[str] = None
    log_file: Optional[str] = None


# ---------------------------------------------------------------------------
# Diagnostic results
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    fix_hint: Optional[str] = None


@dataclass
class PrerequisiteReport:
    service_name: str
    checks: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> List[CheckResult]:
        return [c for c in self.checks if not c.passed]
