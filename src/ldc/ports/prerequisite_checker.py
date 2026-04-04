"""Port: verifies host prerequisites for a service."""
from abc import ABC, abstractmethod

from ldc.domain.models import Prerequisites, PrerequisiteReport


class IPrerequisiteChecker(ABC):

    @abstractmethod
    def check(self, service_name: str, prereqs: Prerequisites) -> PrerequisiteReport:
        """
        Run all prerequisite checks for *service_name*.

        Always returns a report — never raises.  Failures are captured as
        CheckResult entries with passed=False and a human-readable fix_hint.
        """

    @abstractmethod
    def auto_fix(self, service_name: str, prereqs: Prerequisites) -> PrerequisiteReport:
        """
        Attempt to auto-fix fixable prerequisites (e.g. create missing folders)
        and return an updated report.
        """
