"""Adapter: health check via arbitrary command exit code / output."""
from __future__ import annotations

import subprocess
import time

from ldc.domain.models import HealthCheckConfig, HealthCheckType
from ldc.ports.health_checker import IHealthChecker


class CommandHealthChecker(IHealthChecker):

    def supports(self, config: HealthCheckConfig) -> bool:
        return config.type == HealthCheckType.COMMAND

    def check(self, config: HealthCheckConfig) -> bool:
        if not config.command:
            return False
        try:
            result = subprocess.run(
                config.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return False
            if config.expected_output:
                return config.expected_output in (result.stdout + result.stderr)
            return True
        except Exception:
            return False

    def wait_healthy(self, config: HealthCheckConfig) -> bool:
        deadline = time.monotonic() + config.timeout_seconds
        while time.monotonic() < deadline:
            if self.check(config):
                return True
            time.sleep(config.interval_seconds)
        return False
