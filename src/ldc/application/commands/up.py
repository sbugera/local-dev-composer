"""
Use case: bring up services in dependency order.

Steps per service:
  1. Resolve startup order via topological sort
  2. Check prerequisites (fail fast if critical ones are missing)
  3. Start the process
  4. Wait for health check to pass
  5. Mark healthy (or failed) and proceed to the next service
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from ldc.application.env_resolver import resolve_env
from ldc.domain.graph import DependencyGraph
from ldc.domain.models import (
    HealthCheckType,
    Runtime,
    ServiceState,
    ServiceStatus,
    WorkspaceConfig,
)
from ldc.ports.health_checker import IHealthChecker
from ldc.ports.prerequisite_checker import IPrerequisiteChecker
from ldc.ports.process_runner import IProcessRunner
from ldc.ports.reporter import IReporter


class UpCommand:

    def __init__(
        self,
        runner: IProcessRunner,
        health: IHealthChecker,
        checker: IPrerequisiteChecker,
        reporter: IReporter,
    ) -> None:
        self._runner = runner
        self._health = health
        self._checker = checker
        self._reporter = reporter

    def execute(
        self,
        config: WorkspaceConfig,
        service_names: Optional[List[str]] = None,
        group_name: Optional[str] = None,
        skip_checks: bool = False,
        skip_install: bool = True,
        states: Optional[Dict[str, ServiceState]] = None,
        config_dir: str = ".",
    ) -> Dict[str, ServiceState]:
        """
        Start services.  Returns the final states dict.
        If *states* is provided it is used as the shared live-dashboard dict.
        """
        targets = self._resolve_targets(config, service_names, group_name)

        graph = DependencyGraph.from_services(config.services)
        order = graph.startup_order(targets)

        if states is None:
            states = {}

        # Initialise pending state for every service we're about to start
        for name in order:
            if name not in states or states[name].status not in (
                ServiceStatus.HEALTHY, ServiceStatus.STARTING
            ):
                states[name] = ServiceState(name=name, status=ServiceStatus.PENDING)

        self._reporter.start_live_dashboard(states)

        try:
            for name in order:
                svc = config.services[name]
                state = states[name]

                # Skip already-healthy services
                if state.status == ServiceStatus.HEALTHY and self._runner.is_alive(state):
                    self._reporter.info(f"[{name}] Already running (pid {state.pid}) — skipping")
                    continue

                # --- Prerequisite check ---
                if not skip_checks and svc.requires:
                    report = self._checker.check(name, svc.requires)
                    if not report.passed:
                        failures = "; ".join(f.name for f in report.failures)
                        self._reporter.error(
                            f"[{name}] Prerequisite failures: {failures}"
                        )
                        state.status = ServiceStatus.FAILED
                        state.last_error = f"Prerequisite failures: {failures}"
                        continue

                # --- External services with no start command ---
                if svc.runtime == Runtime.EXTERNAL and not svc.start:
                    if svc.health_check:
                        state.status = ServiceStatus.STARTING
                        healthy = self._health.wait_healthy(svc.health_check)
                        state.status = ServiceStatus.HEALTHY if healthy else ServiceStatus.UNHEALTHY
                        if not healthy:
                            self._reporter.warning(
                                f"[{name}] External service unreachable — continuing anyway"
                            )
                    else:
                        state.status = ServiceStatus.SKIPPED
                    continue

                if not svc.start:
                    self._reporter.warning(f"[{name}] No start config — skipping")
                    state.status = ServiceStatus.SKIPPED
                    continue

                # --- Start the process ---
                working_dir = self._resolve_dir(
                    config.root, svc.name, svc.dir, svc.start.working_dir
                )
                log_file = str(Path(config.log_dir) / f"{name}.log")
                env = resolve_env(svc.env, svc.env_files, config_dir)

                state.status = ServiceStatus.STARTING
                self._reporter.info(f"[{name}] Starting…")

                try:
                    new_state = self._runner.start(svc, working_dir, env, log_file)
                    state.pid = new_state.pid
                    state.started_at = new_state.started_at
                    state.log_file = new_state.log_file
                except Exception as exc:
                    state.status = ServiceStatus.FAILED
                    state.last_error = str(exc)
                    self._reporter.error(f"[{name}] Failed to start: {exc}")
                    continue

                # --- Health check ---
                if svc.health_check:
                    if svc.health_check.type == HealthCheckType.PROCESS:
                        # Poll is_alive for PROCESS type
                        healthy = self._wait_process_alive(state, svc.health_check.timeout_seconds)
                    else:
                        healthy = self._health.wait_healthy(svc.health_check)

                    if healthy:
                        state.status = ServiceStatus.HEALTHY
                        state.last_health_check_at = datetime.now(timezone.utc).isoformat()
                        self._reporter.success(f"[{name}] Healthy (pid {state.pid})")
                    else:
                        state.status = ServiceStatus.UNHEALTHY
                        state.last_error = "Health check timed out"
                        self._reporter.error(f"[{name}] Health check failed — check log: {log_file}")
                else:
                    # No health check: assume healthy if process is alive
                    time.sleep(1)
                    if self._runner.is_alive(state):
                        state.status = ServiceStatus.HEALTHY
                        self._reporter.success(f"[{name}] Started (pid {state.pid})")
                    else:
                        state.status = ServiceStatus.FAILED
                        state.last_error = "Process exited immediately"
                        self._reporter.error(f"[{name}] Process exited — check log: {log_file}")

        finally:
            self._reporter.stop_live_dashboard()

        return states

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _wait_process_alive(self, state: ServiceState, timeout: int) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._runner.is_alive(state):
                return True
            time.sleep(1)
        return False

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
