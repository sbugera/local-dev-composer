"""Use case: view or follow a service log file."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

from ldc.domain.models import WorkspaceConfig
from ldc.ports.process_runner import IProcessRunner
from ldc.ports.reporter import IReporter


class LogsCommand:

    def __init__(self, runner: IProcessRunner, reporter: IReporter) -> None:
        self._runner = runner
        self._reporter = reporter

    def execute(
        self,
        config: WorkspaceConfig,
        service_name: str,
        follow: bool = False,
        tail: int = 50,
        log_dir: Optional[str] = None,
    ) -> None:
        state = self._runner.get_state(service_name)
        log_file: Optional[str] = None

        if state and state.log_file:
            log_file = state.log_file
        else:
            # Fall back to default log path
            base = log_dir or config.log_dir
            log_file = str(Path(base) / f"{service_name}.log")

        path = Path(log_file)
        if not path.exists():
            self._reporter.warning(f"No log file found for '{service_name}': {log_file}")
            return

        self._reporter.info(f"Log file: {log_file}")

        if follow:
            self._tail_follow(path)
        else:
            self._tail_static(path, tail)

    # ------------------------------------------------------------------

    @staticmethod
    def _tail_static(path: Path, n: int) -> None:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines[-n:]:
            print(line)

    @staticmethod
    def _tail_follow(path: Path) -> None:
        """Streaming tail -f equivalent."""
        print(f"Following {path} — press Ctrl+C to stop\n")
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            # Jump to end
            fh.seek(0, 2)
            try:
                while True:
                    line = fh.readline()
                    if line:
                        sys.stdout.write(line)
                        sys.stdout.flush()
                    else:
                        time.sleep(0.2)
            except KeyboardInterrupt:
                pass
