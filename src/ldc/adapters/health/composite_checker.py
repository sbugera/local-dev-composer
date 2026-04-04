"""
Adapter: dispatches health checks to the appropriate concrete checker
based on HealthCheckConfig.type.
"""
from __future__ import annotations

import time
from typing import List

from ldc.domain.models import HealthCheckConfig
from ldc.ports.health_checker import IHealthChecker


class CompositeHealthChecker(IHealthChecker):
    """Routes to the first registered checker that supports the config type."""

    def __init__(self, checkers: List[IHealthChecker]) -> None:
        self._checkers = checkers

    def supports(self, config: HealthCheckConfig) -> bool:
        return any(c.supports(config) for c in self._checkers)

    def check(self, config: HealthCheckConfig) -> bool:
        checker = self._find(config)
        if checker is None:
            return False
        return checker.check(config)

    def wait_healthy(self, config: HealthCheckConfig) -> bool:
        checker = self._find(config)
        if checker is None:
            return False
        return checker.wait_healthy(config)

    def _find(self, config: HealthCheckConfig) -> "IHealthChecker | None":
        for c in self._checkers:
            if c.supports(config):
                return c
        return None
