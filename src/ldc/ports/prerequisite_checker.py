"""Port: verifies host prerequisites for a service."""
from abc import ABC, abstractmethod
from typing import Dict, Optional

from ldc.domain.models import Prerequisites, PrerequisiteReport


class IPrerequisiteChecker(ABC):

    @abstractmethod
    def check(
        self,
        service_name: str,
        prereqs: Prerequisites,
        env: Optional[Dict[str, str]] = None,
    ) -> PrerequisiteReport:
        """
        Run all prerequisite checks for *service_name*.

        Always returns a report — never raises.  Failures are captured as
        CheckResult entries with passed=False and a human-readable fix_hint.

        env: resolved per-service environment (system + env_files + inline).
             Runtime checks use it to locate the correct binary, e.g. JAVA_HOME
             picks which JDK is checked rather than the system default.
        """

    @abstractmethod
    def auto_fix(
        self,
        service_name: str,
        prereqs: Prerequisites,
        env: Optional[Dict[str, str]] = None,
    ) -> PrerequisiteReport:
        """Auto-fix fixable prerequisites (e.g. create missing folders) and return an updated report."""
