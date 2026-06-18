"""
Use case: full diagnostic report — checks everything and suggests fixes.

Doctor runs:
  1. Prerequisite checks for all (or selected) services
  2. Git clone status
  3. Process alive status
  4. Port conflicts
  5. Summary with prioritised action list
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ldc.domain.models import Runtime, ServiceStatus, WorkspaceConfig
from ldc.ports.git_client import IGitClient
from ldc.ports.prerequisite_checker import IPrerequisiteChecker
from ldc.ports.process_runner import IProcessRunner
from ldc.ports.reporter import IReporter


class DoctorCommand:

    def __init__(
        self,
        checker: IPrerequisiteChecker,
        git: IGitClient,
        runner: IProcessRunner,
        reporter: IReporter,
    ) -> None:
        self._checker = checker
        self._git = git
        self._runner = runner
        self._reporter = reporter

    def execute(
        self,
        config: WorkspaceConfig,
        service_names: Optional[List[str]] = None,
    ) -> None:
        targets = list(service_names or config.services.keys())
        actions: List[str] = []

        self._reporter.info("Running diagnostics…\n")

        # --- 1. Prerequisites ---
        prereq_reports = []
        for name in targets:
            svc = config.services.get(name)
            if svc and svc.requires:
                report = self._checker.check(name, svc.requires)
                prereq_reports.append(report)
                for failure in report.failures:
                    actions.append(
                        f"[{name}] Fix prerequisite '{failure.name}': "
                        f"{failure.fix_hint or failure.message}"
                    )

        if prereq_reports:
            self._reporter.print_prerequisite_report(prereq_reports)

        # --- 2. Repository clone status ---
        self._reporter.info("\n--- Repository Status ---")
        for name in targets:
            svc = config.services.get(name)
            if not svc or svc.runtime == Runtime.EXTERNAL or not svc.repo:
                continue

            dest = (
                Path(svc.dir) if svc.dir else Path(config.root) / name
            )
            cloned = self._git.is_cloned(dest)
            if cloned:
                try:
                    branch = self._git.current_branch(dest)
                    self._reporter.success(f"[{name}] Cloned at {dest} (branch: {branch})")
                except Exception:
                    self._reporter.success(f"[{name}] Cloned at {dest}")
            else:
                self._reporter.error(f"[{name}] NOT cloned — run: ldc clone {name}")
                actions.append(f"[{name}] Run: ldc clone {name}")

        # --- 3. Process / health status ---
        self._reporter.info("\n--- Process Status ---")
        for name in targets:
            state = self._runner.get_state(name)
            if state is None or state.status in (
                ServiceStatus.STOPPED, ServiceStatus.PENDING
            ):
                self._reporter.info(f"[{name}] Not running")
            elif not self._runner.is_alive(state):
                self._reporter.warning(
                    f"[{name}] PID {state.pid} is no longer alive "
                    f"(was: {state.status.value})"
                )
                if state.log_file:
                    actions.append(
                        f"[{name}] Crashed — inspect log: {state.log_file}"
                    )
                state.status = ServiceStatus.FAILED
                state.last_error = "Process no longer running"
                self._runner.note_exit(state)
            else:
                self._reporter.success(
                    f"[{name}] Running (pid {state.pid}, status: {state.status.value})"
                )

        # --- 4. Action summary ---
        if actions:
            self._reporter.info(
                f"\n{'='*60}\n"
                f"ACTION REQUIRED ({len(actions)} items):\n"
            )
            for i, action in enumerate(actions, 1):
                self._reporter.warning(f"  {i}. {action}")
        else:
            self._reporter.success("\nAll checks passed — environment looks healthy!")
