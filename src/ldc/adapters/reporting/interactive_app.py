"""
Adapter: Textual interactive TUI dashboard for ldc service orchestration.

Layout
------
┌─ ldc — local-dev-composer ──────────────────────────────────┐
│  Service         Status     PID    Started    Runtime        │
│  postgres        HEALTHY    1234   10:30:01   external       │  ← DataTable (2fr)
│  gateway       ▶ STARTING   —      —          java           │    arrow keys select
│  user-service    PENDING    —      —          node           │
├── Details ──── Logs ─────────────────────────────────────── │  ← TabbedContent (3fr)
│  Service:  gateway                                           │
│  Runtime:  java  ·  Depends: postgres                        │
│  Status:   ◌ starting…                                       │
└─ [q] Quit  [↑↓] Select service  [Tab] Switch panel ─────────┘

Requires: pip install "local-dev-composer[ui]"   (textual>=0.50)
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)
from rich.text import Text

from ldc.adapters.reporting.interactive_reporter import InteractiveReporter
from ldc.domain.models import ServiceState, ServiceStatus, WorkspaceConfig


# Status → (symbol, Rich colour)
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

_MSG_STYLE: Dict[str, str] = {
    "info":    "dim",
    "success": "green",
    "warning": "yellow",
    "error":   "bold red",
}

_CSS = """
Screen {
    layout: vertical;
}

#services-table {
    height: 2fr;
    border: solid $primary;
}

#detail-panel {
    height: 3fr;
    border: solid $primary;
}

#details-content {
    padding: 1 2;
    overflow-y: auto;
}

#log-view {
    height: 1fr;
}

#message-bar {
    height: 1;
    background: $panel;
    padding: 0 1;
    color: $text-muted;
}
"""


class LdcInteractiveApp(App):
    """Interactive TUI dashboard for ldc service orchestration."""

    TITLE = "ldc — local-dev-composer"
    CSS = _CSS
    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        states: Dict[str, ServiceState],
        config: WorkspaceConfig,
        reporter: InteractiveReporter,
        task_fn: Callable,
    ) -> None:
        super().__init__()
        self._states = states
        self._config = config
        self._reporter = reporter
        self._task_fn = task_fn
        self._selected: Optional[str] = None
        self._log_cancel = threading.Event()

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="services-table", cursor_type="row")
        with TabbedContent(id="detail-panel"):
            with TabPane("Details", id="tab-details"):
                yield Static("Select a service to view details.", id="details-content")
            with TabPane("Logs", id="tab-logs"):
                yield RichLog(id="log-view", highlight=True, markup=True, wrap=True)
        yield Label("", id="message-bar")
        yield Footer()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_column("", key="icon", width=2)
        table.add_column("Service", key="name", width=24)
        table.add_column("Status", key="status", width=14)
        table.add_column("PID", key="pid", width=8)
        table.add_column("Started", key="started", width=19)
        table.add_column("Runtime", key="runtime", width=10)

        for name in sorted(self._config.services):
            svc = self._config.services[name]
            state = self._states.get(name, ServiceState(name=name))
            symbol, style = _STATUS_STYLE.get(state.status.value, ("?", "white"))
            table.add_row(
                Text(symbol, style=style),
                name,
                Text(state.status.value, style=style),
                str(state.pid or "—"),
                state.started_at[:19] if state.started_at else "—",
                svc.runtime.value,
                key=name,
            )

        names = sorted(self._config.services.keys())
        if names:
            self._selected = names[0]
            self._update_details(self._selected)
            self._start_log_stream(self._selected)

        self.set_interval(0.5, self._refresh)
        self._run_command()

    # ------------------------------------------------------------------
    # Background command worker
    # ------------------------------------------------------------------

    @work(thread=True, name="command")
    def _run_command(self) -> None:
        """Execute the ldc command (up / bootstrap) in a background thread."""
        try:
            self._task_fn()
            self.call_from_thread(
                self._show_message, "success",
                "All services processed — press q to quit"
            )
        except Exception as exc:
            self.call_from_thread(self._show_message, "error", f"Command failed: {exc}")

    # ------------------------------------------------------------------
    # Periodic refresh (runs in the Textual event loop every 500ms)
    # ------------------------------------------------------------------

    def _refresh(self) -> None:
        table = self.query_one(DataTable)
        for name, state in list(self._states.items()):
            symbol, style = _STATUS_STYLE.get(state.status.value, ("?", "white"))
            try:
                table.update_cell(name, "icon", Text(symbol, style=style), update_width=False)
                table.update_cell(name, "status", Text(state.status.value, style=style), update_width=False)
                table.update_cell(name, "pid", str(state.pid or "—"), update_width=False)
                if state.started_at:
                    table.update_cell(name, "started", state.started_at[:19], update_width=False)
            except Exception:
                pass

        if self._selected:
            self._update_details(self._selected)

        for level, msg in self._reporter.drain_messages():
            self._show_message(level, msg)

    # ------------------------------------------------------------------
    # Row selection
    # ------------------------------------------------------------------

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is None:
            return
        name = str(event.row_key.value)
        if name != self._selected:
            self._selected = name
            self._update_details(name)
            self._start_log_stream(name)

    # ------------------------------------------------------------------
    # Details panel
    # ------------------------------------------------------------------

    def _update_details(self, name: str) -> None:
        state = self._states.get(name, ServiceState(name=name))
        svc = self._config.services.get(name)
        if not svc:
            return

        symbol, style = _STATUS_STYLE.get(state.status.value, ("?", "white"))
        lines = [
            f"[bold]Service:[/bold]  {name}",
            f"[bold]Runtime:[/bold]  {svc.runtime.value}",
            f"[bold]Status:[/bold]   [{style}]{symbol} {state.status.value}[/{style}]",
            f"[bold]PID:[/bold]      {state.pid or '—'}",
            f"[bold]Started:[/bold]  {state.started_at[:19] if state.started_at else '—'}",
            f"[bold]Depends:[/bold]  {', '.join(svc.depends_on) if svc.depends_on else '(none)'}",
        ]
        if svc.health_check:
            lines.append(f"[bold]Health:[/bold]   {svc.health_check.type.value}")
        if svc.description:
            lines.append(f"[bold]Desc:[/bold]     {svc.description}")
        if state.last_error:
            lines.append(f"[bold red]Error:[/bold red]    {state.last_error}")
        if state.log_file:
            lines.append(f"[bold]Log:[/bold]      {state.log_file}")

        self.query_one("#details-content", Static).update("\n".join(lines))

    # ------------------------------------------------------------------
    # Log streaming
    # ------------------------------------------------------------------

    def _start_log_stream(self, name: str) -> None:
        """Cancel the existing log worker and start a new one for *name*."""
        self._log_cancel.set()
        self._log_cancel = threading.Event()

        log_widget = self.query_one("#log-view", RichLog)
        log_widget.clear()

        state = self._states.get(name)
        log_file = (
            state.log_file if (state and state.log_file)
            else str(Path(self._config.log_dir) / f"{name}.log")
        )
        self._stream_log_file(log_file, self._log_cancel)

    @work(thread=True, name="log-stream")
    def _stream_log_file(self, log_file: str, cancel: threading.Event) -> None:
        """Tail *log_file* and write new lines into the RichLog widget."""
        path = Path(log_file)

        # Wait up to 10 s for the file to appear (service may not have started yet)
        deadline = time.monotonic() + 10
        while not path.exists():
            if cancel.is_set():
                return
            if time.monotonic() > deadline:
                self.call_from_thread(
                    self.query_one("#log-view", RichLog).write,
                    f"[dim]No log file yet: {log_file}[/dim]",
                )
                return
            time.sleep(0.3)

        with path.open("r", encoding="utf-8", errors="replace") as fh:
            # Show last 200 lines on initial open
            all_lines = fh.readlines()
            initial = all_lines[-200:] if len(all_lines) > 200 else all_lines
            log_widget = self.query_one("#log-view", RichLog)
            for line in initial:
                if cancel.is_set():
                    return
                self.call_from_thread(log_widget.write, line.rstrip())

            # Follow new lines
            while not cancel.is_set():
                line = fh.readline()
                if line:
                    self.call_from_thread(log_widget.write, line.rstrip())
                else:
                    time.sleep(0.1)

    # ------------------------------------------------------------------
    # Message bar
    # ------------------------------------------------------------------

    def _show_message(self, level: str, message: str) -> None:
        style = _MSG_STYLE.get(level, "white")
        self.query_one("#message-bar", Label).update(Text(message[:120], style=style))

    # ------------------------------------------------------------------
    # Key action
    # ------------------------------------------------------------------

    def action_quit(self) -> None:
        self._log_cancel.set()
        self.exit()
