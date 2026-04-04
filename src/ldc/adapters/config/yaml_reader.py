"""
Adapter: reads a composer.yml file and produces a WorkspaceConfig.

YAML schema is deliberately flat and human-friendly; this adapter maps it
to the rich domain model.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from ldc.domain.exceptions import ConfigValidationError
from ldc.domain.models import (
    Group,
    HealthCheckConfig,
    HealthCheckType,
    InstallConfig,
    Prerequisites,
    Runtime,
    Service,
    StartConfig,
    VenvConfig,
    WorkspaceConfig,
)
from ldc.ports.config_reader import IConfigReader


class YamlConfigReader(IConfigReader):

    def read(self, path: Path) -> WorkspaceConfig:
        if not path.exists():
            raise ConfigValidationError(f"Config file not found: {path}")

        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)

        if not isinstance(raw, dict):
            raise ConfigValidationError("composer.yml must be a YAML mapping")

        workspace_raw = raw.get("workspace", {})
        root = workspace_raw.get("root", "./services")
        log_dir = workspace_raw.get("log_dir", "./logs")

        services_raw: Dict[str, Any] = raw.get("services", {})
        groups_raw: Dict[str, Any] = raw.get("groups", {})

        services = {
            name: self._parse_service(name, svc_raw)
            for name, svc_raw in services_raw.items()
        }

        groups = {
            name: self._parse_group(name, grp_raw)
            for name, grp_raw in groups_raw.items()
        }

        return WorkspaceConfig(
            root=root,
            log_dir=log_dir,
            services=services,
            groups=groups,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_service(self, name: str, raw: Dict[str, Any]) -> Service:
        runtime_str = raw.get("runtime", "custom")
        try:
            runtime = Runtime(runtime_str.lower())
        except ValueError:
            raise ConfigValidationError(
                f"Service '{name}': unknown runtime '{runtime_str}'. "
                f"Valid values: {[r.value for r in Runtime]}"
            )

        return Service(
            name=name,
            runtime=runtime,
            depends_on=raw.get("depends_on", []),
            repo=raw.get("repo"),
            branch=raw.get("branch", "main"),
            dir=raw.get("dir"),
            env=raw.get("env", {}),
            env_files=self._parse_env_files(raw),
            requires=self._parse_prerequisites(raw.get("requires")),
            venv=self._parse_venv(raw.get("venv")),
            install=self._parse_install(raw.get("install")),
            start=self._parse_start(raw.get("start")),
            health_check=self._parse_health_check(name, raw.get("health_check")),
            labels=raw.get("labels", {}),
            description=raw.get("description", ""),
        )

    def _parse_venv(self, raw: Optional[Any]) -> Optional[VenvConfig]:
        if not raw:
            return None
        if raw is True:
            return VenvConfig()
        return VenvConfig(
            path=raw.get("path", ".venv"),
            python=raw.get("python", "python"),
        )

    def _parse_env_files(self, raw: Dict[str, Any]) -> list:
        if "env_files" in raw:
            value = raw["env_files"]
            return [value] if isinstance(value, str) else list(value)
        if "env_file" in raw:
            value = raw["env_file"]
            return [value] if value else []
        return []

    def _parse_prerequisites(self, raw: Optional[Dict]) -> Optional[Prerequisites]:
        if not raw:
            return None
        return Prerequisites(
            java=raw.get("java"),
            python=raw.get("python"),
            node=raw.get("node"),
            dotnet=raw.get("dotnet"),
            commands=raw.get("commands", []),
            env_vars=raw.get("env_vars", []),
            folders=raw.get("folders", []),
            files=raw.get("files", []),
            ports_free=raw.get("ports_free", []),
        )

    def _parse_install(self, raw: Optional[Any]) -> Optional[InstallConfig]:
        if not raw:
            return None
        if isinstance(raw, str):
            return InstallConfig(command=raw)
        return InstallConfig(
            command=raw["command"],
            working_dir=raw.get("working_dir", "."),
        )

    def _parse_start(self, raw: Optional[Any]) -> Optional[StartConfig]:
        if not raw:
            return None
        if isinstance(raw, str):
            return StartConfig(command=raw)
        return StartConfig(
            command=raw["command"],
            args=raw.get("args", []),
            working_dir=raw.get("working_dir", "."),
        )

    def _parse_health_check(
        self, service_name: str, raw: Optional[Dict]
    ) -> Optional[HealthCheckConfig]:
        if not raw:
            return None

        type_str = raw.get("type", "process")
        try:
            hc_type = HealthCheckType(type_str.lower())
        except ValueError:
            raise ConfigValidationError(
                f"Service '{service_name}': unknown health_check type '{type_str}'"
            )

        return HealthCheckConfig(
            type=hc_type,
            url=raw.get("url"),
            host=raw.get("host", "localhost"),
            port=raw.get("port"),
            command=raw.get("command"),
            expected_output=raw.get("expected_output"),
            interval_seconds=raw.get("interval", 5),
            timeout_seconds=raw.get("timeout", 60),
            retries=raw.get("retries", 12),
        )

    def _parse_group(self, name: str, raw: Dict[str, Any]) -> Group:
        return Group(
            name=name,
            description=raw.get("description", ""),
            services=raw.get("services", []),
        )
