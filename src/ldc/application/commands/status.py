"""Use case: display current status of all (or selected) services."""
from __future__ import annotations

from typing import Dict, List, Optional

from ldc.domain.models import ServiceState, ServiceStatus, WorkspaceConfig
from ldc.ports.process_runner import IProcessRunner
from ldc.ports.reporter import IReporter


class StatusCommand:

    def __init__(self, runner: IProcessRunner, reporter: IReporter) -> None:
        self._runner = runner
        self._reporter = reporter

    def execute(
        self,
        config: WorkspaceConfig,
        service_names: Optional[List[str]] = None,
    ) -> None:
        targets = list(service_names or config.services.keys())
        states: Dict[str, ServiceState] = {}

        for name in targets:
            state = self._runner.get_state(name)
            if state is None:
                state = ServiceState(name=name, status=ServiceStatus.STOPPED)
            else:
                # Reconcile: process may have died since last save
                if state.pid and not self._runner.is_alive(state):
                    state.status = ServiceStatus.STOPPED
                    state.pid = None
            states[name] = state

        self._reporter.print_status_table(states)
