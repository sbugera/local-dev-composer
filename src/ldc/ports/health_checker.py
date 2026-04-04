"""Port: verifies that a running service has reached a healthy state."""
from abc import ABC, abstractmethod

from ldc.domain.models import HealthCheckConfig


class IHealthChecker(ABC):

    @abstractmethod
    def supports(self, config: HealthCheckConfig) -> bool:
        """Return True if this checker handles the given HealthCheckConfig type."""

    @abstractmethod
    def check(self, config: HealthCheckConfig) -> bool:
        """
        Perform a single health probe.

        Returns True if healthy, False otherwise.
        Must not raise — catch internal errors and return False.
        """

    @abstractmethod
    def wait_healthy(self, config: HealthCheckConfig) -> bool:
        """
        Poll until the service is healthy or the timeout is exceeded.

        Returns True if healthy within timeout, False otherwise.
        """
