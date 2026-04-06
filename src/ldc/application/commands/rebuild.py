"""Use case: stop → install → start services (full rebuild cycle)."""
from __future__ import annotations

import time
from typing import List, Optional

from ldc.application.commands.down import DownCommand
from ldc.application.commands.install import InstallCommand
from ldc.application.commands.up import UpCommand
from ldc.domain.models import WorkspaceConfig
from ldc.ports.reporter import IReporter


class RebuildCommand:

    def __init__(
        self,
        down_cmd: DownCommand,
        install_cmd: InstallCommand,
        up_cmd: UpCommand,
        reporter: IReporter,
    ) -> None:
        self._down = down_cmd
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

        # Stop all targets first (reverse dependency order)
        self._reporter.info("Stopping services…")
        self._down.execute(config, service_names=targets)

        # Install all targets in parallel; track which ones failed
        self._reporter.info("")
        self._reporter.info("Installing services…")
        failed_install = self._install.execute(
            config, service_names=targets, config_dir=config_dir, workers=workers
        )

        # Start only services whose install succeeded
        to_start = [n for n in targets if n not in failed_install]
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
        self._reporter.info(f"Rebuild complete in {time.monotonic() - total_start:.1f}s")

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
