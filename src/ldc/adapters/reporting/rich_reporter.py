"""
Adapter: rich-library reporter — coloured tables, live dashboard, panels.
Falls back gracefully if 'rich' is not installed.
"""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional

from ldc.domain.models import PrerequisiteReport, ServiceState, ServiceStatus
from ldc.ports.reporter import IReporter

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# Status → (symbol, rich colour)
_STATUS_STYLE: Dict[str, tuple] = {
    ServiceStatus.PENDING.value:    ("○", "dim"),
    ServiceStatus.STARTING.value:   ("◌", "yellow"),
    ServiceStatus.HEALTHY.value:    ("●", "green"),
    ServiceStatus.UNHEALTHY.value:  ("●", "red"),
    ServiceStatus.STOPPED.value:    ("○", "dim"),
    ServiceStatus.FAILED.value:     ("✗", "bold red"),
    ServiceStatus.SKIPPED.value:    ("—", "dim"),
    ServiceStatus.INSTALLING.value: ("⟳", "cyan"),
    ServiceStatus.CLONING.value:    ("⟳", "cyan"),
}


class RichReporter(IReporter):

    def __init__(self) -> None:
        self._console = Console() if RICH_AVAILABLE else None
        self._live: Optional["Live"] = None
        self._live_states: Optional[Dict[str, ServiceState]] = None
        self._live_thread: Optional[threading.Thread] = None
        self._live_stop = threading.Event()

    # ------------------------------------------------------------------
    # Simple log messages
    # ------------------------------------------------------------------

    def info(self, message: str) -> None:
        if RICH_AVAILABLE:
            self._console.print(f"[dim]ℹ[/dim]  {message}")
        else:
            print(f"  {message}")

    def success(self, message: str) -> None:
        if RICH_AVAILABLE:
            self._console.print(f"[green]✔[/green]  {message}")
        else:
            print(f"✔ {message}")

    def warning(self, message: str) -> None:
        if RICH_AVAILABLE:
            self._console.print(f"[yellow]⚠[/yellow]  {message}")
        else:
            print(f"⚠ {message}")

    def error(self, message: str) -> None:
        if RICH_AVAILABLE:
            self._console.print(f"[bold red]✗[/bold red]  {message}")
        else:
            print(f"✗ {message}")

    # ------------------------------------------------------------------
    # Static status table
    # ------------------------------------------------------------------

    def print_status_table(self, states: Dict[str, ServiceState]) -> None:
        if not RICH_AVAILABLE:
            self._plain_status(states)
            return

        table = self._build_status_table(states)
        self._console.print(table)

    def _build_status_table(self, states: Dict[str, ServiceState]) -> "Table":
        table = Table(
            title="Service Status",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold",
        )
        table.add_column("Service", min_width=20)
        table.add_column("Status", min_width=12)
        table.add_column("PID", justify="right", min_width=7)
        table.add_column("Started", min_width=22)
        table.add_column("Last Error", min_width=30)

        for name, state in sorted(states.items()):
            symbol, style = _STATUS_STYLE.get(
                state.status.value, ("?", "white")
            )
            status_text = Text(f"{symbol} {state.status.value}", style=style)
            table.add_row(
                name,
                status_text,
                str(state.pid or "—"),
                state.started_at[:19] if state.started_at else "—",
                (state.last_error or "")[:60],
            )
        return table

    # ------------------------------------------------------------------
    # Live dashboard
    # ------------------------------------------------------------------

    def start_live_dashboard(self, states: Dict[str, ServiceState]) -> None:
        if not RICH_AVAILABLE:
            return

        self._live_states = states
        self._live_stop.clear()
        self._live = Live(
            self._build_status_table(states),
            console=self._console,
            refresh_per_second=2,
            screen=False,
        )
        self._live.start()

        def _refresh() -> None:
            while not self._live_stop.is_set():
                if self._live and self._live_states is not None:
                    self._live.update(self._build_status_table(self._live_states))
                time.sleep(0.5)

        self._live_thread = threading.Thread(target=_refresh, daemon=True)
        self._live_thread.start()

    def stop_live_dashboard(self) -> None:
        self._live_stop.set()
        if self._live_thread:
            self._live_thread.join(timeout=2)
        if self._live:
            self._live.stop()
            self._live = None

    # ------------------------------------------------------------------
    # Prerequisite report
    # ------------------------------------------------------------------

    def print_prerequisite_report(self, reports: List[PrerequisiteReport]) -> None:
        if not RICH_AVAILABLE:
            self._plain_prereq(reports)
            return

        for report in reports:
            all_passed = report.passed
            title_style = "green" if all_passed else "red"
            title = f"[{title_style}]{report.service_name}[/{title_style}]"

            table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
            table.add_column("Check")
            table.add_column("Result", min_width=8)
            table.add_column("Details")
            table.add_column("Fix hint")

            for chk in report.checks:
                result_text = Text(
                    "PASS" if chk.passed else "FAIL",
                    style="green" if chk.passed else "bold red",
                )
                table.add_row(
                    chk.name,
                    result_text,
                    chk.message,
                    chk.fix_hint or "",
                )

            self._console.print(Panel(table, title=title, expand=False))

    # ------------------------------------------------------------------
    # Plain fallbacks (no rich)
    # ------------------------------------------------------------------

    def _plain_status(self, states: Dict[str, ServiceState]) -> None:
        print(f"\n{'SERVICE':<25} {'STATUS':<12} {'PID':<8} {'STARTED'}")
        print("-" * 70)
        for name, state in sorted(states.items()):
            print(
                f"{name:<25} {state.status.value:<12} "
                f"{str(state.pid or '-'):<8} {state.started_at or '-'}"
            )

    def _plain_prereq(self, reports: List[PrerequisiteReport]) -> None:
        for report in reports:
            print(f"\n=== {report.service_name} ===")
            for chk in report.checks:
                mark = "PASS" if chk.passed else "FAIL"
                print(f"  [{mark}] {chk.name}: {chk.message}")
                if not chk.passed and chk.fix_hint:
                    print(f"         FIX: {chk.fix_hint}")
