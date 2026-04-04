"""Port: reads and parses workspace configuration."""
from abc import ABC, abstractmethod
from pathlib import Path

from ldc.domain.models import WorkspaceConfig


class IConfigReader(ABC):
    @abstractmethod
    def read(self, path: Path) -> WorkspaceConfig:
        """Parse config file at *path* and return a validated WorkspaceConfig."""
