"""Use case: stop running services in reverse dependency order."""
from __future__ import annotations

import time
from typing import Dict, List, Optional

from ldc.domain.graph import DependencyGraph
from ldc.domain.models import ServiceState, ServiceStatus, WorkspaceConfig
from ldc.ports.process_runner import IProcessRunner
from ldc.ports.reporter import IReporter
from ldc.ports.state_store import IStateStore


class DownCommand:

    def __init__(
        self,
        runner: IProcessRunner,
        store: IStateStore,
        reporter: IReporter,
    ) -> None:
        self._runner = runner
        self._store = store
        self._reporter = reporter

    def execute(
        self,
        config: WorkspaceConfig,
        service_names: Optional[List[str]] = None,
        timeout_seconds: int = 15,
    ) -> None:
        targets = list(service_names or config.services.keys())

        graph = DependencyGraph.from_services(config.services)
        # When stopping specific services, stop only what was asked — do not
        # pull in transitive dependencies (they may be shared by other services).
        # When stopping all services, use full reverse-dependency order so that
        # dependents are stopped before the services they rely on.
        if service_names:
            order = graph.shutdown_order_explicit(targets)
        else:
            order = graph.shutdown_order(targets)

        for name in order:
            state = self._runner.get_state(name)
            if state is None or state.pid is None:
                self._reporter.info(f"[{name}] Not running — skipping")
                continue

            if not self._runner.is_alive(state):
                self._reporter.info(f"[{name}] Process already gone")
                state.status = ServiceStatus.STOPPED
                continue

            self._reporter.info(f"[{name}] Stopping (pid {state.pid})…")
            t = time.monotonic()
            try:
                self._runner.stop(state, timeout_seconds)
                self._reporter.success(f"[{name}] Stopped ({time.monotonic()-t:.1f}s)")
            except Exception as exc:
                self._reporter.error(f"[{name}] Stop error: {exc} ({time.monotonic()-t:.1f}s)")
