"""
Adapter: starts and manages OS processes on Windows.

Each service process:
  - Runs in its own subprocess with a fully-isolated environment
  - Stdout/stderr are streamed to a per-service log file
  - Is tracked by PID and persisted via IStateStore
"""
from __future__ import annotations

import os
import shlex
import shutil
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
        cmd = self._resolve_executable(cmd, env)
        log_fh = open(log_file, "a", encoding="utf-8", buffering=1)  # line-buffered

        # Write a session header to the log
        ts = datetime.now(timezone.utc).isoformat()
        display_cmd = service.start.command
        if service.start.args:
            display_cmd += " " + " ".join(service.start.args)
        log_fh.write(f"\n{'='*60}\n")
        log_fh.write(f"[LDC] Starting '{service.name}' at {ts}\n")
        log_fh.write(f"[LDC] Command: {display_cmd}\n")
        log_fh.write(f"{'='*60}\n")
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
            self._write_footer(state, "EXITED (process already gone)")
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

        self._write_footer(state, "STOPPED")
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

    def reload_states(self) -> None:
        self._states = self._store.load()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    _SHELL_OPS = frozenset({"&&", "||", "|", ">", ">>", "<", "2>", "2>>"})

    def _build_command(self, service: Service) -> list:
        cfg = service.start
        full_cmd = cfg.command
        if cfg.args:
            full_cmd += " " + " ".join(cfg.args)

        # Pass args directly when possible — cmd.exe corrupts quoted/multi-line args.
        # Check tokens (not raw string) so `->` inside a string isn't mistaken for `>`.
        try:
            parts = shlex.split(full_cmd.strip(), posix=True)
            if not any(p in self._SHELL_OPS for p in parts):
                return parts
        except ValueError:
            pass

        return ["cmd", "/c", full_cmd]

    @staticmethod
    def _resolve_executable(parts: list, env: Dict[str, str]) -> list:
        """Resolve a bare executable name using the service env's PATH.

        CreateProcess on Windows uses the *parent* process PATH to find the
        executable, ignoring the env dict passed to the child. Resolving here
        with the service env's PATH ensures JAVA_HOME/bin (and equivalents)
        are searched instead of whatever ldc itself has on PATH.
        """
        if len(parts) < 1 or os.sep in parts[0] or "/" in parts[0]:
            return parts
        path_key = next((k for k in env if k.upper() == "PATH"), "PATH")
        resolved = shutil.which(parts[0], path=env.get(path_key, ""))
        return [resolved, *parts[1:]] if resolved else parts

    @staticmethod
    def _write_footer(state: ServiceState, status: str) -> None:
        """Append a finish footer (timestamp, status, elapsed) to the service log."""
        if not state.log_file:
            return
        finished = datetime.now(timezone.utc)
        elapsed = ""
        if state.started_at:
            try:
                started = datetime.fromisoformat(state.started_at)
                elapsed = f" — elapsed {(finished - started).total_seconds():.1f}s"
            except ValueError:
                pass
        try:
            with open(state.log_file, "a", encoding="utf-8") as fh:
                fh.write(f"\n{'='*60}\n")
                fh.write(f"[LDC] Stopped '{state.name}' at {finished.isoformat()}\n")
                fh.write(f"[LDC] Status: {status}{elapsed}\n")
                fh.write(f"{'='*60}\n")
        except OSError:
            pass

    def _persist(self) -> None:
        self._store.save(self._states)
