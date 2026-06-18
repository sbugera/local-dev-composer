"""Port: manages OS-level processes for services."""
from abc import ABC, abstractmethod
from typing import Dict, Optional

from ldc.domain.models import Service, ServiceState, StartConfig


class IProcessRunner(ABC):

    @abstractmethod
    def start(
        self,
        service: Service,
        working_dir: str,
        env: Dict[str, str],
        log_file: str,
    ) -> ServiceState:
        """
        Start the service process.

        Returns a ServiceState with at least a pid and STARTING status.
        The caller is responsible for polling health afterwards.
        """

    @abstractmethod
    def stop(self, state: ServiceState, timeout_seconds: int = 15) -> None:
        """Gracefully terminate the process, then force-kill if it outlasts timeout."""

    @abstractmethod
    def is_alive(self, state: ServiceState) -> bool:
        """Return True if the process referenced by *state* is still running."""

    @abstractmethod
    def get_state(self, service_name: str) -> Optional[ServiceState]:
        """Return the last known ServiceState for *service_name*, or None."""

    @abstractmethod
    def update_state(self, state: ServiceState) -> None:
        """Persist an updated ServiceState (e.g. after health check resolves)."""

    @abstractmethod
    def note_exit(self, state: ServiceState, status: str = "CRASHED (process exited)") -> None:
        """
        Record that a process exited outside ldc's control (e.g. a crash
        detected during a status poll): append a finish footer to its log,
        clear the pid, and persist. Idempotent — does nothing if *state* has
        no pid, so repeated detections will not write duplicate footers.
        """

    @abstractmethod
    def reload_states(self) -> None:
        """Re-read persisted state from the store, discarding any in-memory-only changes."""
