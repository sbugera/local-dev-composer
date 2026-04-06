"""Use case: run install commands for services."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional

from ldc.application.env_resolver import resolve_env
from ldc.domain.models import Runtime, WorkspaceConfig
from ldc.ports.installer import IInstaller
from ldc.ports.reporter import IReporter


class InstallCommand:

    def __init__(self, installer: IInstaller, reporter: IReporter) -> None:
        self._installer = installer
        self._reporter = reporter

    def execute(
        self,
        config: WorkspaceConfig,
        service_names: Optional[List[str]] = None,
        config_dir: str = ".",
        workers: int = 1,
    ) -> None:
        targets = list(service_names or config.services.keys())

        def _install_one(name: str) -> None:
            svc = config.services.get(name)
            if svc is None:
                self._reporter.warning(f"Unknown service '{name}' — skipping install")
                return
            if not svc.install:
                self._reporter.info(f"[{name}] No install command — skipping")
                return
            if svc.runtime == Runtime.EXTERNAL:
                self._reporter.info(f"[{name}] External service — skipping install")
                return

            working_dir = self._resolve_dir(config.root, svc.name, svc.dir, svc.install.working_dir)
            log_file = str(Path(config.log_dir) / f"{name}-install.log")
            env = resolve_env(svc.env, svc.env_files, config_dir)

            self._reporter.info(f"[{name}] Installing: {svc.install.command}")
            t = time.monotonic()
            try:
                self._installer.install(name, svc.install, working_dir, env, log_file)
                self._reporter.success(f"[{name}] Install complete ({time.monotonic()-t:.1f}s)")
            except Exception as exc:
                self._reporter.error(f"[{name}] Install failed: {exc} ({time.monotonic()-t:.1f}s)")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_install_one, targets))

    @staticmethod
    def _resolve_dir(
        workspace_root: str,
        name: str,
        service_dir: Optional[str],
        working_dir: str,
    ) -> str:
        base = Path(service_dir) if service_dir else Path(workspace_root) / name
        resolved = base / working_dir if working_dir != "." else base
        return str(resolved)
