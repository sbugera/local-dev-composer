"""Use case: run install commands for services."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Set, Tuple

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
    ) -> Set[str]:
        """
        Run install commands for the given services.
        Returns the set of service names that failed.
        """
        targets = list(service_names or config.services.keys())
        failed: Set[str] = set()

        def _install_one(name: str) -> Tuple[str, bool, List[Tuple[str, str]]]:
            """Run install for one service; return (name, ok, messages)."""
            msgs: List[Tuple[str, str]] = []
            ok = True
            svc = config.services.get(name)
            if svc is None:
                msgs.append(("warning", f"Unknown service '{name}' — skipping install"))
                return name, ok, msgs
            if not svc.install:
                msgs.append(("info", f"[{name}] No install command — skipping"))
                return name, ok, msgs
            if svc.runtime == Runtime.EXTERNAL:
                msgs.append(("info", f"[{name}] External service — skipping install"))
                return name, ok, msgs

            working_dir = self._resolve_dir(config.root, svc.name, svc.dir, svc.install.working_dir)
            log_file = str(Path(config.log_dir) / f"{name}-install.log")
            env = resolve_env(svc.env, svc.env_files, config_dir)

            msgs.append(("info", f"[{name}] Installing: {svc.install.command}"))
            t = time.monotonic()
            try:
                self._installer.install(name, svc.install, working_dir, env, log_file)
                msgs.append(("success", f"[{name}] Install complete ({time.monotonic()-t:.1f}s)"))
            except Exception as exc:
                msgs.append(("error", f"[{name}] Install failed: {exc} ({time.monotonic()-t:.1f}s)"))
                ok = False
            return name, ok, msgs

        group = len(targets) > 1
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_install_one, name): name for name in targets}
            first = True
            for future in as_completed(futures):
                name, ok, msgs = future.result()
                if not ok:
                    failed.add(name)
                if msgs:
                    if group and not first:
                        self._reporter.info("")
                    for method, msg in msgs:
                        getattr(self._reporter, method)(msg)
                    first = False

        return failed

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
