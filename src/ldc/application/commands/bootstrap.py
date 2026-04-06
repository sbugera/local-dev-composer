"""Use case: clone → install → start services (full onboarding sequence)."""
from __future__ import annotations

import time
from typing import List, Optional

from ldc.application.commands.clone import CloneCommand
from ldc.application.commands.install import InstallCommand
from ldc.application.commands.up import UpCommand
from ldc.domain.models import WorkspaceConfig
from ldc.ports.reporter import IReporter


class BootstrapCommand:

    def __init__(
        self,
        clone_cmd: CloneCommand,
        install_cmd: InstallCommand,
        up_cmd: UpCommand,
        reporter: IReporter,
    ) -> None:
        self._clone = clone_cmd
        self._install = install_cmd
        self._up = up_cmd
        self._reporter = reporter

    def execute(
        self,
        config: WorkspaceConfig,
        service_names: Optional[List[str]] = None,
        group_name: Optional[str] = None,
        skip_checks: bool = False,
        config_dir: str = ".",
        workers: int = 1,
    ) -> None:
        targets = self._resolve_targets(config, service_names, group_name)
        total_start = time.monotonic()

        # Clone all targets in parallel — get back the set of failures
        self._reporter.info("Cloning repositories…")
        failed: set = self._clone.execute(config, service_names=targets, workers=workers)

        # Install all non-failed targets in parallel
        to_install = [n for n in targets if n not in failed]
        if to_install:
            self._reporter.info("")
            self._reporter.info("Installing services…")
            install_failed = self._install.execute(
                config, service_names=to_install, config_dir=config_dir, workers=workers
            )
            failed |= install_failed

        # Start — skip services that failed to clone or install
        to_start = [n for n in targets if n not in failed]
        if to_start:
            self._reporter.info("")
            self._reporter.info("Starting services…")
            self._up.execute(
                config,
                service_names=to_start,
                skip_checks=skip_checks,
                config_dir=config_dir,
                workers=workers,
            )

        self._reporter.info("")
        self._reporter.info(f"Bootstrap complete in {time.monotonic() - total_start:.1f}s")

    @staticmethod
    def _resolve_targets(
        config: WorkspaceConfig,
        service_names: Optional[List[str]],
        group_name: Optional[str],
    ) -> List[str]:
        if group_name:
            group = config.groups.get(group_name)
            if not group:
                raise ValueError(
                    f"Unknown group '{group_name}'. "
                    f"Available: {list(config.groups.keys())}"
                )
            return group.services
        if service_names:
            return service_names
        return list(config.services.keys())
