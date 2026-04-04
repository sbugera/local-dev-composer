"""Adapter: HTTP/HTTPS health check."""
from __future__ import annotations

import time
import urllib.request
import urllib.error

from ldc.domain.models import HealthCheckConfig, HealthCheckType
from ldc.ports.health_checker import IHealthChecker


class HttpHealthChecker(IHealthChecker):

    def supports(self, config: HealthCheckConfig) -> bool:
        return config.type == HealthCheckType.HTTP

    def check(self, config: HealthCheckConfig) -> bool:
        try:
            req = urllib.request.Request(config.url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                return 200 <= resp.status < 400
        except Exception:
            return False

    def wait_healthy(self, config: HealthCheckConfig) -> bool:
        deadline = time.monotonic() + config.timeout_seconds
        while time.monotonic() < deadline:
            if self.check(config):
                return True
            time.sleep(config.interval_seconds)
        return False
