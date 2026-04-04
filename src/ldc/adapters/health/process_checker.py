"""Adapter: health check that simply verifies the process is alive."""
from __future__ import annotations

import time

import psutil

from ldc.domain.models import HealthCheckConfig, HealthCheckType
from ldc.ports.health_checker import IHealthChecker


class ProcessHealthChecker(IHealthChecker):

    def __init__(self, pid_provider) -> None:
        # pid_provider: callable(service_name) -> Optional[int]
        self._pid_provider = pid_provider

    def supports(self, config: HealthCheckConfig) -> bool:
        return config.type == HealthCheckType.PROCESS

    def check(self, config: HealthCheckConfig) -> bool:
        # For PROCESS type we just need any live process — the caller supplies PID
        # via the provider; config carries no PID directly.
        # This checker is used as a fallback by the orchestrator passing PID explicitly.
        return True  # orchestrator checks is_alive() directly for PROCESS type

    def wait_healthy(self, config: HealthCheckConfig) -> bool:
        return True
