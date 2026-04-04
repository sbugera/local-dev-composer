"""Port: persists and restores runtime service state across sessions."""
from abc import ABC, abstractmethod
from typing import Dict

from ldc.domain.models import ServiceState


class IStateStore(ABC):

    @abstractmethod
    def save(self, states: Dict[str, ServiceState]) -> None:
        """Persist all service states to durable storage."""

    @abstractmethod
    def load(self) -> Dict[str, ServiceState]:
        """Restore previously persisted states. Returns empty dict if none."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all persisted state."""
