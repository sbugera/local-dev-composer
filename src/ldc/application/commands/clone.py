"""Use case: clone (or update) service repositories."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Set, Tuple

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
        workers: int = 1,
    ) -> Set[str]:
        """
        Clone or pull the given services (all services if *service_names* is None).

        Services with runtime=EXTERNAL or no repo are silently skipped.
        When *pull* is True, updates an already-cloned repo instead of cloning.
        When *workers* > 1, clones run in parallel.
        Returns the set of service names that failed.
        """
        targets = list(service_names or config.services.keys())
        failed: Set[str] = set()

        def _clone_one(name: str) -> Tuple[str, bool, List[Tuple[str, str]]]:
            """Run clone for one service; return (name, ok, messages)."""
            msgs: List[Tuple[str, str]] = []
            ok = True
            svc = config.services.get(name)
            if svc is None:
                msgs.append(("warning", f"Unknown service '{name}' — skipping clone"))
                return name, ok, msgs

            if svc.runtime == Runtime.EXTERNAL or not svc.repo:
                msgs.append(("info", f"[{name}] No repo configured — skipping"))
                return name, ok, msgs

            dest = self._resolve_dir(config.root, svc.name, svc.dir)

            if self._git.is_cloned(dest):
                if pull:
                    msgs.append(("info", f"[{name}] Pulling latest from {svc.branch}…"))
                    t = time.monotonic()
                    try:
                        self._git.pull(dest, svc.branch)
                        msgs.append(("success", f"[{name}] Up to date ({time.monotonic()-t:.1f}s)"))
                    except Exception as exc:
                        msgs.append(("error", f"[{name}] Pull failed: {exc} ({time.monotonic()-t:.1f}s)"))
                        ok = False
                else:
                    msgs.append(("info", f"[{name}] Already cloned at {dest} — skipping"))
            else:
                msgs.append(("info", f"[{name}] Cloning {svc.repo} @ {svc.branch} → {dest}…"))
                t = time.monotonic()
                try:
                    self._git.clone(svc.repo, dest, svc.branch)
                    msgs.append(("success", f"[{name}] Cloned successfully ({time.monotonic()-t:.1f}s)"))
                except Exception as exc:
                    msgs.append(("error", f"[{name}] Clone failed: {exc} ({time.monotonic()-t:.1f}s)"))
                    ok = False
            return name, ok, msgs

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_clone_one, name): name for name in targets}
            for future in as_completed(futures):
                name, ok, msgs = future.result()
                if not ok:
                    failed.add(name)
                for method, msg in msgs:
                    getattr(self._reporter, method)(msg)

        return failed

    @staticmethod
    def _resolve_dir(workspace_root: str, name: str, override: Optional[str]) -> Path:
        if override:
            return Path(override)
        return Path(workspace_root) / name
