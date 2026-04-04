"""Port: reports progress and status to the user."""
from abc import ABC, abstractmethod
from typing import Dict, List

from ldc.domain.models import PrerequisiteReport, ServiceState


class IReporter(ABC):

    @abstractmethod
    def info(self, message: str) -> None:
        """Emit an informational message."""

    @abstractmethod
    def success(self, message: str) -> None:
        """Emit a success message."""

    @abstractmethod
    def warning(self, message: str) -> None:
        """Emit a warning message."""

    @abstractmethod
    def error(self, message: str) -> None:
        """Emit an error message."""

    @abstractmethod
    def print_status_table(self, states: Dict[str, ServiceState]) -> None:
        """Render a status table for all services."""

    @abstractmethod
    def print_prerequisite_report(self, reports: List[PrerequisiteReport]) -> None:
        """Render prerequisite check results."""

    @abstractmethod
    def start_live_dashboard(self, states: Dict[str, ServiceState]) -> None:
        """
        Start a live-updating dashboard that reflects state changes.
        *states* is the shared dict mutated by the orchestrator.
        """

    @abstractmethod
    def stop_live_dashboard(self) -> None:
        """Stop the live dashboard (restore normal terminal output)."""
