"""Use case: check (and optionally fix) prerequisites for services."""
from __future__ import annotations

from typing import List, Optional

from ldc.application.env_resolver import resolve_env
from ldc.domain.models import WorkspaceConfig
from ldc.ports.prerequisite_checker import IPrerequisiteChecker
from ldc.ports.reporter import IReporter


class CheckCommand:

    def __init__(
        self,
        checker: IPrerequisiteChecker,
        reporter: IReporter,
    ) -> None:
        self._checker = checker
        self._reporter = reporter

    def execute(
        self,
        config: WorkspaceConfig,
        service_names: Optional[List[str]] = None,
        auto_fix: bool = False,
        config_dir: str = ".",
    ) -> bool:
        """Returns True if all checks passed, False otherwise."""
        targets = list(service_names or config.services.keys())
        reports = []

        for name in targets:
            svc = config.services.get(name)
            if svc is None:
                self._reporter.warning(f"Unknown service '{name}' — skipping check")
                continue
            if not svc.requires:
                self._reporter.info(f"[{name}] No prerequisites defined — skipping")
                continue

            env = resolve_env(svc.env, svc.env_files, config_dir, svc.path_dirs)
            if auto_fix:
                report = self._checker.auto_fix(name, svc.requires, env)
            else:
                report = self._checker.check(name, svc.requires, env)

            reports.append(report)

        if reports:
            self._reporter.print_prerequisite_report(reports)

        all_passed = all(r.passed for r in reports)
        if all_passed:
            self._reporter.success("All prerequisite checks passed.")
        else:
            failed_services = [r.service_name for r in reports if not r.passed]
            self._reporter.error(
                f"Prerequisites failed for: {', '.join(failed_services)}"
            )
            if not auto_fix:
                self._reporter.info("Tip: run  ldc check --fix  to auto-fix where possible")

        return all_passed
