"""
Adapter: Textual interactive TUI dashboard for ldc service orchestration.

Opens as a status viewer. Use keybindings to run commands on the selected
service or all services.

Layout
------
┌─ ldc — local-dev-composer ──────────────────────────────────┐
│  Service         Status     PID    Started    Runtime        │  ← DataTable
│  postgres        HEALTHY    1234   10:30:01   external       │    arrow keys select
│  gateway       ▶ STARTING   —      —          java           │
├── Details ──── Logs ─────────────────────────────────────── │  ← TabbedContent
│  Service:  gateway                                           │
│  Runtime:  java  ·  Depends: postgres                        │
│  Status:   ◌ starting…                                       │
└─ [u]Up [d]Down [i]Install [c]Clone [k]Check [U]Up All ───────┘

Requires: pip install "local-dev-composer[ui]"   (textual>=0.50)
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

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
from ldc.application.container import Container
from ldc.domain.models import ServiceState, ServiceStatus, WorkspaceConfig


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
    """Interactive TUI dashboard — viewer + command launcher."""

    TITLE = "ldc — local-dev-composer"
    CSS = _CSS
    BINDINGS = [
        Binding("u", "service_up",       "Up"),
        Binding("d", "service_down",     "Down"),
        Binding("r", "service_restart",  "Restart"),
        Binding("b", "service_rebuild",  "Rebuild"),
        Binding("i", "service_install",  "Install"),
        Binding("c", "service_clone",    "Clone"),
        Binding("k", "service_check",    "Check"),
        Binding("w", "toggle_wrap",      "Wrap"),
        Binding("y", "copy_log",         "Copy Log"),
        Binding("U", "all_up",           "Up All",      show=False),
        Binding("D", "all_down",         "Down All",    show=False),
        Binding("R", "all_restart",      "Restart All", show=False),
        Binding("B", "all_rebuild",      "Rebuild All", show=False),
        Binding("I", "all_install",      "Install All", show=False),
        Binding("C", "all_clone",        "Clone All",   show=False),
        Binding("K", "all_check",        "Check All",   show=False),
        Binding("q", "quit",             "Quit"),
    ]

    def __init__(
        self,
        container: Container,
        config: WorkspaceConfig,
        reporter: InteractiveReporter,
        config_dir: str = ".",
        ldc_dir: Path = Path(".ldc"),
    ) -> None:
        super().__init__()
        self._container = container
        self._config = config
        self._reporter = reporter
        self._config_dir = config_dir
        self._ui_config_path = ldc_dir / "ui.json"
        self._states: Dict[str, ServiceState] = {}
        self._selected: Optional[str] = None
        self._log_cancel = threading.Event()
        self._log_lines: List[str] = []
        self._busy = False
        self._refresh_tick = 0

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

        # Load current states from the state store (viewer mode)
        for name in sorted(self._config.services):
            stored = self._container.runner.get_state(name)
            self._states[name] = stored if stored is not None else ServiceState(name=name)

        for name in sorted(self._config.services):
            svc = self._config.services[name]
            state = self._states[name]
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
        self._show_message(
            "info",
            "u/d/r/b/i/c/k — Up/Down/Restart/Rebuild/Install/Clone/Check  "
            "U/D/R/B/I/C/K — same for All  q:Quit",
        )

        # Restore persisted theme (must be last — Textual triggers watch_theme on set)
        try:
            data = json.loads(self._ui_config_path.read_text(encoding="utf-8"))
            if "theme" in data:
                self.theme = data["theme"]
        except (OSError, json.JSONDecodeError):
            pass

    def watch_theme(self, theme: str) -> None:
        try:
            data: dict = {}
            if self._ui_config_path.exists():
                try:
                    data = json.loads(self._ui_config_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    pass
            data["theme"] = theme
            self._ui_config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Periodic refresh
    # ------------------------------------------------------------------

    _SYNC_EVERY = 4  # ticks — sync from disk every 4 × 0.5s = 2 seconds

    def _refresh(self) -> None:
        self._refresh_tick += 1
        if self._refresh_tick % self._SYNC_EVERY == 0:
            self._sync_states()

        table = self.query_one(DataTable)
        for name, state in list(self._states.items()):
            symbol, style = _STATUS_STYLE.get(state.status.value, ("?", "white"))
            try:
                table.update_cell(name, "icon",   Text(symbol, style=style), update_width=False)
                table.update_cell(name, "status", Text(state.status.value, style=style), update_width=False)
                table.update_cell(name, "pid",    str(state.pid or "—"), update_width=False)
                if state.started_at:
                    table.update_cell(name, "started", state.started_at[:19], update_width=False)
            except Exception:
                pass

        if self._selected:
            self._update_details(self._selected)

        for level, msg in self._reporter.drain_messages():
            self._show_message(level, msg)

    def _sync_states(self) -> None:
        """Reload state.json and verify process liveness for running services."""
        self._container.runner.reload_states()
        for name in self._config.services:
            stored = self._container.runner.get_state(name)
            if stored is not None:
                self._states[name] = stored

        # For services that look alive on disk, verify the process still exists
        _alive = {ServiceStatus.HEALTHY, ServiceStatus.STARTING}
        for state in self._states.values():
            if state.status in _alive and state.pid is not None:
                if not self._container.runner.is_alive(state):
                    state.status = ServiceStatus.FAILED
                    state.last_error = "Process no longer running"
                    self._container.runner.note_exit(state)

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
        self._log_cancel.set()
        self._log_cancel = threading.Event()
        self._log_lines = []

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
        path = Path(log_file)

        deadline = time.monotonic() + 5
        while not path.exists():
            if cancel.is_set():
                return
            if time.monotonic() > deadline:
                self.call_from_thread(
                    self.query_one("#log-view", RichLog).write,
                    f"[dim]No log file: {log_file}[/dim]",
                )
                return
            time.sleep(0.3)

        TAIL_LINES = 200
        TAIL_BYTES = 131072  # 128 KB — enough for ~200 typical log lines without reading the whole file

        # Seek to near the end in binary mode — avoids loading multi-GB files into memory
        with path.open("rb") as raw:
            raw.seek(0, 2)
            file_size = raw.tell()
            start_pos = max(0, file_size - TAIL_BYTES)
            raw.seek(start_pos)
            chunk = raw.read()

        lines = chunk.decode("utf-8", errors="replace").splitlines()
        if start_pos > 0 and lines:
            lines = lines[1:]  # drop potentially partial first line at the cut point
        initial = lines[-TAIL_LINES:]

        if cancel.is_set():
            return

        self._log_lines = list(initial)
        log_widget = self.query_one("#log-view", RichLog)
        # Write all initial lines in one UI dispatch so the view opens at the bottom
        self.call_from_thread(lambda: [log_widget.write(ln) for ln in initial])

        # Open a fresh handle positioned at EOF so readline() only returns new content
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(0, 2)
            while not cancel.is_set():
                line = fh.readline()
                if line:
                    stripped = line.rstrip()
                    self._log_lines.append(stripped)
                    if len(self._log_lines) > 2000:
                        self._log_lines = self._log_lines[-1000:]
                    self.call_from_thread(log_widget.write, stripped)
                else:
                    time.sleep(0.1)

    # ------------------------------------------------------------------
    # Log actions
    # ------------------------------------------------------------------

    def action_toggle_wrap(self) -> None:
        log_widget = self.query_one("#log-view", RichLog)
        log_widget.wrap = not log_widget.wrap
        if self._selected:
            self._start_log_stream(self._selected)

    def action_copy_log(self) -> None:
        if not self._log_lines:
            self._show_message("warning", "No log content to copy")
            return
        text = "\n".join(self._log_lines)
        try:
            subprocess.run("clip", input=text, encoding="utf-8", shell=True, check=True)
            self._show_message("success", f"Copied {len(self._log_lines)} lines to clipboard")
        except Exception as exc:
            self._show_message("error", f"Copy failed: {exc}")

    # ------------------------------------------------------------------
    # Background command runner
    # ------------------------------------------------------------------

    def _run_in_bg(self, label: str, fn: Callable) -> None:
        if self._busy:
            self._show_message("warning", "A command is already running — please wait")
            return
        self._busy = True
        self._show_message("info", f"Running: {label}…")
        self._execute_bg(fn, label)

    @work(thread=True, name="command")
    def _execute_bg(self, fn: Callable, label: str) -> None:
        try:
            fn()
            self.call_from_thread(self._show_message, "success", f"{label} — done")
        except Exception as exc:
            self.call_from_thread(self._show_message, "error", f"{label} failed: {exc}")
        finally:
            self._busy = False
            self.call_from_thread(self._reload_states)

    def _reload_states(self) -> None:
        """Refresh states from the state store after a command completes."""
        for name in self._config.services:
            stored = self._container.runner.get_state(name)
            if stored is not None:
                self._states[name] = stored

    # ------------------------------------------------------------------
    # Actions — selected service
    # ------------------------------------------------------------------

    def action_service_up(self) -> None:
        if not self._selected:
            return
        name = self._selected
        workers = self._config.workers
        self._run_in_bg(f"up {name}", lambda: self._container.up_cmd.execute(
            self._config,
            service_names=[name],
            states=self._states,
            config_dir=self._config_dir,
            workers=workers,
        ))

    def action_service_down(self) -> None:
        if not self._selected:
            return
        name = self._selected
        self._run_in_bg(f"down {name}", lambda: self._container.down_cmd.execute(
            self._config,
            service_names=[name],
        ))

    def action_service_install(self) -> None:
        if not self._selected:
            return
        name = self._selected
        workers = self._config.workers
        self._run_in_bg(f"install {name}", lambda: self._container.install_cmd.execute(
            self._config,
            service_names=[name],
            config_dir=self._config_dir,
            workers=workers,
        ))

    def action_service_clone(self) -> None:
        if not self._selected:
            return
        name = self._selected
        self._run_in_bg(f"clone {name}", lambda: self._container.clone_cmd.execute(
            self._config,
            service_names=[name],
        ))

    def action_service_check(self) -> None:
        if not self._selected:
            return
        name = self._selected
        self._run_in_bg(f"check {name}", lambda: self._container.check_cmd.execute(
            self._config,
            service_names=[name],
        ))

    def action_service_restart(self) -> None:
        if not self._selected:
            return
        name = self._selected
        workers = self._config.workers
        self._run_in_bg(f"restart {name}", lambda: self._container.restart_cmd.execute(
            self._config,
            service_names=[name],
            config_dir=self._config_dir,
            workers=workers,
        ))

    def action_service_rebuild(self) -> None:
        if not self._selected:
            return
        name = self._selected
        workers = self._config.workers
        self._run_in_bg(f"rebuild {name}", lambda: self._container.rebuild_cmd.execute(
            self._config,
            service_names=[name],
            config_dir=self._config_dir,
            workers=workers,
        ))

    # ------------------------------------------------------------------
    # Actions — global
    # ------------------------------------------------------------------

    def action_all_up(self) -> None:
        workers = self._config.workers
        self._run_in_bg("up all", lambda: self._container.up_cmd.execute(
            self._config,
            states=self._states,
            config_dir=self._config_dir,
            workers=workers,
        ))

    def action_all_down(self) -> None:
        self._run_in_bg("down all", lambda: self._container.down_cmd.execute(
            self._config,
        ))

    def action_all_restart(self) -> None:
        workers = self._config.workers
        self._run_in_bg("restart all", lambda: self._container.restart_cmd.execute(
            self._config,
            config_dir=self._config_dir,
            workers=workers,
        ))

    def action_all_rebuild(self) -> None:
        workers = self._config.workers
        self._run_in_bg("rebuild all", lambda: self._container.rebuild_cmd.execute(
            self._config,
            config_dir=self._config_dir,
            workers=workers,
        ))

    def action_all_install(self) -> None:
        workers = self._config.workers
        self._run_in_bg("install all", lambda: self._container.install_cmd.execute(
            self._config,
            config_dir=self._config_dir,
            workers=workers,
        ))

    def action_all_clone(self) -> None:
        workers = self._config.workers
        self._run_in_bg("clone all", lambda: self._container.clone_cmd.execute(
            self._config,
            workers=workers,
        ))

    def action_all_check(self) -> None:
        self._run_in_bg("check all", lambda: self._container.check_cmd.execute(
            self._config,
        ))

    # ------------------------------------------------------------------
    # Message bar
    # ------------------------------------------------------------------

    def _show_message(self, level: str, message: str) -> None:
        style = _MSG_STYLE.get(level, "white")
        self.query_one("#message-bar", Label).update(Text(message[:120], style=style))

    # ------------------------------------------------------------------
    # Quit
    # ------------------------------------------------------------------

    def action_quit(self) -> None:
        self._log_cancel.set()
        self.exit()
