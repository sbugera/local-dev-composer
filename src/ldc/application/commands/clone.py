"""Use case: clone (or update) service repositories."""
from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

from ldc.domain.models import Runtime, WorkspaceConfig
from ldc.ports.git_client import IGitClient
from ldc.ports.reporter import IReporter


class CloneCommand:

    def __init__(
        self,
        git: IGitClient,
        reporter: IReporter,
    ) -> None:
        self._git = git
        self._reporter = reporter

    def execute(
        self,
        config: WorkspaceConfig,
        service_names: Optional[List[str]] = None,
        pull: bool = False,
    ) -> None:
        """
        Clone or pull the given services (all services if *service_names* is None).

        Services with runtime=EXTERNAL or no repo are silently skipped.
        When *pull* is True, updates an already-cloned repo instead of cloning.
        """
        targets = list(
            (service_names or config.services.keys())
        )

        for name in targets:
            svc = config.services.get(name)
            if svc is None:
                self._reporter.warning(f"Unknown service '{name}' — skipping clone")
                continue

            if svc.runtime == Runtime.EXTERNAL or not svc.repo:
                self._reporter.info(f"[{name}] No repo configured — skipping")
                continue

            dest = self._resolve_dir(config.root, svc.name, svc.dir)

            if self._git.is_cloned(dest):
                if pull:
                    self._reporter.info(f"[{name}] Pulling latest from {svc.branch}…")
                    t = time.monotonic()
                    try:
                        self._git.pull(dest, svc.branch)
                        self._reporter.success(f"[{name}] Up to date ({time.monotonic()-t:.1f}s)")
                    except Exception as exc:
                        self._reporter.error(f"[{name}] Pull failed: {exc} ({time.monotonic()-t:.1f}s)")
                else:
                    self._reporter.info(f"[{name}] Already cloned at {dest} — skipping")
            else:
                self._reporter.info(
                    f"[{name}] Cloning {svc.repo} @ {svc.branch} → {dest}…"
                )
                t = time.monotonic()
                try:
                    self._git.clone(svc.repo, dest, svc.branch)
                    self._reporter.success(f"[{name}] Cloned successfully ({time.monotonic()-t:.1f}s)")
                except Exception as exc:
                    self._reporter.error(f"[{name}] Clone failed: {exc} ({time.monotonic()-t:.1f}s)")

    @staticmethod
    def _resolve_dir(workspace_root: str, name: str, override: Optional[str]) -> Path:
        if override:
            return Path(override)
        return Path(workspace_root) / name
