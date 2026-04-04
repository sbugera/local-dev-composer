"""Port: runs the install step for a service."""
from abc import ABC, abstractmethod
from typing import Dict

from ldc.domain.models import InstallConfig


class IInstaller(ABC):

    @abstractmethod
    def install(
        self,
        service_name: str,
        config: InstallConfig,
        working_dir: str,
        env: Dict[str, str],
        log_file: str,
    ) -> None:
        """
        Execute the install command for a service.

        Streams output to *log_file*.
        Raises on non-zero exit code.
        """
