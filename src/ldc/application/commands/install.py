"""Use case: run install commands for services."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ldc.application.env_resolver import resolve_env
from ldc.application.venv_manager import VenvManager
from ldc.domain.models import Runtime, WorkspaceConfig
from ldc.ports.installer import IInstaller
from ldc.ports.reporter import IReporter


class InstallCommand:

    def __init__(
        self,
        installer: IInstaller,
        reporter: IReporter,
    ) -> None:
        self._installer = installer
        self._reporter = reporter
        self._venv = VenvManager()

    def execute(
        self,
        config: WorkspaceConfig,
        service_names: Optional[List[str]] = None,
        config_dir: str = ".",
    ) -> None:
        targets = list(service_names or config.services.keys())

        for name in targets:
            svc = config.services.get(name)
            if svc is None:
                self._reporter.warning(f"Unknown service '{name}' — skipping install")
                continue
            if not svc.install:
                self._reporter.info(f"[{name}] No install command — skipping")
                continue
            if svc.runtime == Runtime.EXTERNAL:
                self._reporter.info(f"[{name}] External service — skipping install")
                continue

            working_dir = self._resolve_dir(config.root, svc.name, svc.dir, svc.install.working_dir)
            log_file = str(Path(config.log_dir) / f"{name}-install.log")
            env = resolve_env(svc.env, svc.env_files, config_dir)
            if svc.venv:
                env.update(self._venv.ensure(svc.venv, working_dir))

            self._reporter.info(f"[{name}] Installing: {svc.install.command}")
            try:
                self._installer.install(name, svc.install, working_dir, env, log_file)
                self._reporter.success(f"[{name}] Install complete")
            except Exception as exc:
                self._reporter.error(f"[{name}] Install failed: {exc}")

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
