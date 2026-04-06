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

import threading
import time
from concurrent.futures import ThreadPoolExecutor
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
        workers: int = 1,
    ) -> Dict[str, ServiceState]:
        """
        Start services.  Returns the final states dict.
        If *states* is provided it is used as the shared live-dashboard dict.
        When *workers* > 1, independent services (same dependency level) start in parallel.
        """
        targets = self._resolve_targets(config, service_names, group_name)

        graph = DependencyGraph.from_services(config.services)
        levels = graph.startup_order_parallel(targets)
        order = [name for level in levels for name in level]

        if states is None:
            states = {}

        # Seed from persisted state so already-running services are not lost
        for name in order:
            if name not in states:
                stored = self._runner.get_state(name)
                if stored is not None:
                    states[name] = stored

        # Initialise pending state for every service we're about to start
        for name in order:
            if name not in states or states[name].status not in (
                ServiceStatus.HEALTHY, ServiceStatus.STARTING
            ):
                states[name] = ServiceState(name=name, status=ServiceStatus.PENDING)

        self._reporter.start_live_dashboard(states)

        # When running in parallel, suppress per-service text log calls — the live
        # dashboard table is the primary UI and shows state transitions in real time.
        # In sequential mode (workers=1) text messages are kept for plain output.
        silent = workers > 1

        # Lock for state-store writes (shared JSON file) when running in parallel
        lock = threading.Lock()

        try:
            for level in levels:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    list(pool.map(
                        lambda name: self._start_one(  # noqa: B023
                            name, config, states, skip_checks, config_dir, lock, silent
                        ),
                        level,
                    ))
        finally:
            self._reporter.stop_live_dashboard()

        return states

    def _start_one(
        self,
        name: str,
        config: WorkspaceConfig,
        states: Dict[str, ServiceState],
        skip_checks: bool,
        config_dir: str,
        lock: threading.Lock,
        silent: bool = False,
    ) -> None:
        """Start a single service and update its state.

        When *silent* is True, informational log calls are suppressed — the live
        dashboard table is the primary UI and shows state transitions in real time.
        """
        def _log(method: str, msg: str) -> None:
            if not silent:
                getattr(self._reporter, method)(msg)

        svc = config.services[name]
        state = states[name]

        # Skip already-healthy services
        if state.status == ServiceStatus.HEALTHY and self._runner.is_alive(state):
            _log("info", f"[{name}] Already running (pid {state.pid}) — skipping")
            return

        # Skip if any direct dependency failed
        for dep in svc.depends_on:
            dep_state = states.get(dep)
            if dep_state and dep_state.status == ServiceStatus.FAILED:
                state.status = ServiceStatus.FAILED
                state.last_error = f"Dependency '{dep}' failed"
                with lock:
                    self._runner.update_state(state)
                return

        # --- Prerequisite check ---
        if not skip_checks and svc.requires:
            report = self._checker.check(name, svc.requires)
            if not report.passed:
                failures = "; ".join(f.name for f in report.failures)
                state.status = ServiceStatus.FAILED
                state.last_error = f"Prerequisite failures: {failures}"
                with lock:
                    self._runner.update_state(state)
                return

        # --- External services with no start command ---
        if svc.runtime == Runtime.EXTERNAL and not svc.start:
            if svc.health_check:
                state.status = ServiceStatus.STARTING
                healthy = self._health.wait_healthy(svc.health_check)
                state.status = ServiceStatus.HEALTHY if healthy else ServiceStatus.UNHEALTHY
            else:
                state.status = ServiceStatus.SKIPPED
            with lock:
                self._runner.update_state(state)
            return

        if not svc.start:
            state.status = ServiceStatus.SKIPPED
            with lock:
                self._runner.update_state(state)
            return

        # --- Start the process ---
        working_dir = self._resolve_dir(
            config.root, svc.name, svc.dir, svc.start.working_dir
        )
        log_file = str(Path(config.log_dir) / f"{name}.log")
        env = resolve_env(svc.env, svc.env_files, config_dir)
        state.status = ServiceStatus.STARTING
        _log("info", f"[{name}] Starting…")
        t = time.monotonic()

        try:
            new_state = self._runner.start(svc, working_dir, env, log_file)
            state.pid = new_state.pid
            state.started_at = new_state.started_at
            state.log_file = new_state.log_file
        except Exception as exc:
            state.status = ServiceStatus.FAILED
            state.last_error = str(exc)
            _log("error", f"[{name}] Failed to start: {exc} ({time.monotonic()-t:.1f}s)")
            with lock:
                self._runner.update_state(state)
            return

        # --- Health check ---
        if svc.health_check:
            if svc.health_check.type == HealthCheckType.PROCESS:
                healthy = self._wait_process_alive(state, svc.health_check.timeout_seconds)
            else:
                healthy = self._health.wait_healthy(svc.health_check)

            elapsed = f"{time.monotonic()-t:.1f}s"
            if healthy:
                state.status = ServiceStatus.HEALTHY
                state.last_health_check_at = datetime.now(timezone.utc).isoformat()
                _log("success", f"[{name}] Healthy (pid {state.pid}) ({elapsed})")
            else:
                state.status = ServiceStatus.FAILED
                state.last_error = "Health check timed out"
                _log("error", f"[{name}] Health check failed ({elapsed}) — check log: {log_file}")
                if self._runner.is_alive(state):
                    self._runner.stop(state)
        else:
            time.sleep(1)
            elapsed = f"{time.monotonic()-t:.1f}s"
            if self._runner.is_alive(state):
                state.status = ServiceStatus.HEALTHY
                _log("success", f"[{name}] Started (pid {state.pid}) ({elapsed})")
            else:
                state.status = ServiceStatus.FAILED
                state.last_error = "Process exited immediately"
                _log("error", f"[{name}] Process exited ({elapsed}) — check log: {log_file}")

        with lock:
            self._runner.update_state(state)

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
