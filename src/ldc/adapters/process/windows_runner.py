"""
Adapter: starts and manages OS processes on Windows.

Each service process:
  - Runs in its own subprocess with a fully-isolated environment
  - Stdout/stderr are streamed to a per-service log file
  - Is tracked by PID and persisted via IStateStore
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import psutil

from ldc.domain.models import Service, ServiceState, ServiceStatus
from ldc.ports.process_runner import IProcessRunner
from ldc.ports.state_store import IStateStore


class WindowsProcessRunner(IProcessRunner):

    def __init__(self, state_store: IStateStore) -> None:
        self._store = state_store
        self._states: Dict[str, ServiceState] = state_store.load()

    # ------------------------------------------------------------------
    # IProcessRunner
    # ------------------------------------------------------------------

    def start(
        self,
        service: Service,
        working_dir: str,
        env: Dict[str, str],
        log_file: str,
    ) -> ServiceState:
        if not service.start:
            raise ValueError(f"Service '{service.name}' has no start configuration")

        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        cmd = self._build_command(service)
        log_fh = open(log_file, "a", encoding="utf-8", buffering=1)  # line-buffered

        # Write a session header to the log
        ts = datetime.now(timezone.utc).isoformat()
        log_fh.write(f"\n{'='*60}\n[LDC] Starting '{service.name}' at {ts}\n{'='*60}\n")
        log_fh.flush()

        proc = subprocess.Popen(
            cmd,
            cwd=working_dir,
            env=env,
            stdout=log_fh,
            stderr=log_fh,
            # Windows: create a new process group so we can terminate cleanly
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=False,
        )

        state = ServiceState(
            name=service.name,
            status=ServiceStatus.STARTING,
            pid=proc.pid,
            started_at=ts,
            log_file=log_file,
        )
        self._states[service.name] = state
        self._store.save(self._states)
        return state

    def stop(self, state: ServiceState, timeout_seconds: int = 15) -> None:
        if state.pid is None:
            return

        try:
            parent = psutil.Process(state.pid)
        except psutil.NoSuchProcess:
            state.status = ServiceStatus.STOPPED
            self._persist()
            return

        # Gracefully terminate all children first, then the parent
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass

        try:
            parent.terminate()
        except psutil.NoSuchProcess:
            pass

        gone, alive = psutil.wait_procs(
            [parent] + children, timeout=timeout_seconds
        )

        for proc in alive:
            try:
                proc.kill()
            except psutil.NoSuchProcess:
                pass

        state.status = ServiceStatus.STOPPED
        state.pid = None
        self._persist()

    def is_alive(self, state: ServiceState) -> bool:
        if state.pid is None:
            return False
        try:
            proc = psutil.Process(state.pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False

    def get_state(self, service_name: str) -> Optional[ServiceState]:
        return self._states.get(service_name)

    def update_state(self, state: ServiceState) -> None:
        self._states[state.name] = state
        self._persist()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_command(self, service: Service) -> list:
        cfg = service.start
        parts = cfg.command.split()
        parts.extend(cfg.args)
        return parts

    def _persist(self) -> None:
        self._store.save(self._states)
