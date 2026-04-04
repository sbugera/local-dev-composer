"""
Adapter: persists ServiceState records to a JSON file under .ldc/state.json.

This lets ldc survive restarts — it can detect already-running processes
from a previous session and reattach rather than double-start them.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from ldc.domain.models import ServiceState, ServiceStatus
from ldc.ports.state_store import IStateStore


class JsonStateStore(IStateStore):

    def __init__(self, state_file: Path) -> None:
        self._path = state_file
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, states: Dict[str, ServiceState]) -> None:
        data = {
            name: {
                "status": state.status.value,
                "pid": state.pid,
                "started_at": state.started_at,
                "last_health_check_at": state.last_health_check_at,
                "last_error": state.last_error,
                "log_file": state.log_file,
            }
            for name, state in states.items()
        }
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> Dict[str, ServiceState]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

        states: Dict[str, ServiceState] = {}
        for name, raw in data.items():
            try:
                status = ServiceStatus(raw.get("status", "stopped"))
            except ValueError:
                status = ServiceStatus.STOPPED
            states[name] = ServiceState(
                name=name,
                status=status,
                pid=raw.get("pid"),
                started_at=raw.get("started_at"),
                last_health_check_at=raw.get("last_health_check_at"),
                last_error=raw.get("last_error"),
                log_file=raw.get("log_file"),
            )
        return states

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()
