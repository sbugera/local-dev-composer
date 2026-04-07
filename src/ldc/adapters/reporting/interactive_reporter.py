"""
Adapter: interactive reporter for the Textual TUI dashboard.

start_live_dashboard() / stop_live_dashboard() are no-ops — the Textual app
manages rendering.  Messages are queued for the app to drain each refresh cycle.
"""
from __future__ import annotations

import queue
from typing import Dict, List, Tuple

from ldc.adapters.reporting.rich_reporter import RichReporter
from ldc.domain.models import PrerequisiteReport, ServiceState
from ldc.ports.reporter import IReporter


class InteractiveReporter(IReporter):
    """IReporter for use with the Textual interactive dashboard."""

    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._fallback = RichReporter()

    # ------------------------------------------------------------------
    # Message logging — buffered for the Textual app to consume
    # ------------------------------------------------------------------

    def info(self, message: str) -> None:
        self._queue.put(("info", message))

    def success(self, message: str) -> None:
        self._queue.put(("success", message))

    def warning(self, message: str) -> None:
        self._queue.put(("warning", message))

    def error(self, message: str) -> None:
        self._queue.put(("error", message))

    # ------------------------------------------------------------------
    # Table / report rendering — delegate to RichReporter as fallback
    # (called after app exits, or for non-interactive paths)
    # ------------------------------------------------------------------

    def print_status_table(self, states: Dict[str, ServiceState]) -> None:
        self._fallback.print_status_table(states)

    def print_prerequisite_report(self, reports: List[PrerequisiteReport]) -> None:
        self._fallback.print_prerequisite_report(reports)

    # ------------------------------------------------------------------
    # Live dashboard — no-ops (the Textual app handles rendering)
    # ------------------------------------------------------------------

    def start_live_dashboard(self, states: Dict[str, ServiceState]) -> None:
        pass  # Textual app handles refresh

    def stop_live_dashboard(self) -> None:
        pass  # Textual app handles teardown

    # ------------------------------------------------------------------
    # Queue access for the Textual app
    # ------------------------------------------------------------------

    def drain_messages(self) -> List[Tuple[str, str]]:
        """Return all pending (level, message) tuples without blocking."""
        messages: List[Tuple[str, str]] = []
        while True:
            try:
                messages.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return messages
