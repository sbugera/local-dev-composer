"""
Dependency-injection container.

Wires all ports to their concrete adapter implementations and exposes
pre-built command objects to the CLI layer.
"""
from __future__ import annotations

from pathlib import Path

from ldc.adapters.config.yaml_reader import YamlConfigReader
from ldc.adapters.git.subprocess_client import SubprocessGitClient
from ldc.adapters.health.command_checker import CommandHealthChecker
from ldc.adapters.health.composite_checker import CompositeHealthChecker
from ldc.adapters.health.http_checker import HttpHealthChecker
from ldc.adapters.health.tcp_checker import TcpHealthChecker
from ldc.adapters.prerequisites.system_checker import SystemPrerequisiteChecker
from ldc.adapters.process.windows_runner import WindowsProcessRunner
from ldc.adapters.reporting.rich_reporter import RichReporter
from ldc.adapters.state.json_store import JsonStateStore
from ldc.application.commands.check import CheckCommand
from ldc.application.commands.clone import CloneCommand
from ldc.application.commands.doctor import DoctorCommand
from ldc.application.commands.down import DownCommand
from ldc.application.commands.install import InstallCommand
from ldc.application.commands.logs import LogsCommand
from ldc.application.commands.status import StatusCommand
from ldc.application.commands.up import UpCommand
from ldc.application.installer_service import SubprocessInstaller


class Container:
    """
    Construct once per CLI invocation.  All shared objects are singletons
    within the lifetime of one command execution.
    """

    def __init__(self, ldc_dir: Path = Path(".ldc")) -> None:
        # Core adapters
        self.reporter = RichReporter()
        self.config_reader = YamlConfigReader()
        self.git = SubprocessGitClient()
        self.prereq_checker = SystemPrerequisiteChecker()
        self.installer = SubprocessInstaller()

        state_file = ldc_dir / "state.json"
        self.state_store = JsonStateStore(state_file)

        self.health_checker = CompositeHealthChecker(
            checkers=[
                HttpHealthChecker(),
                TcpHealthChecker(),
                CommandHealthChecker(),
            ]
        )

        self.runner = WindowsProcessRunner(self.state_store)

        # Commands
        self.clone_cmd = CloneCommand(self.git, self.reporter)
        self.check_cmd = CheckCommand(self.prereq_checker, self.reporter)
        self.install_cmd = InstallCommand(self.installer, self.reporter)
        self.up_cmd = UpCommand(
            self.runner, self.health_checker, self.prereq_checker, self.reporter
        )
        self.down_cmd = DownCommand(self.runner, self.state_store, self.reporter)
        self.status_cmd = StatusCommand(self.runner, self.reporter)
        self.logs_cmd = LogsCommand(self.runner, self.reporter)
        self.doctor_cmd = DoctorCommand(
            self.prereq_checker, self.git, self.runner, self.reporter
        )
