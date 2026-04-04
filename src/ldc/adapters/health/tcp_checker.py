"""Adapter: TCP port health check."""
from __future__ import annotations

import socket
import time

from ldc.domain.models import HealthCheckConfig, HealthCheckType
from ldc.ports.health_checker import IHealthChecker


class TcpHealthChecker(IHealthChecker):

    def supports(self, config: HealthCheckConfig) -> bool:
        return config.type == HealthCheckType.TCP

    def check(self, config: HealthCheckConfig) -> bool:
        host = config.host or "localhost"
        port = config.port
        if not port:
            return False
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except (OSError, socket.timeout):
            return False

    def wait_healthy(self, config: HealthCheckConfig) -> bool:
        deadline = time.monotonic() + config.timeout_seconds
        while time.monotonic() < deadline:
            if self.check(config):
                return True
            time.sleep(config.interval_seconds)
        return False
