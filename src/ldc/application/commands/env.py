"""Use case: print the resolved environment for a service."""
from __future__ import annotations

import os
from typing import Optional

from ldc.application.env_resolver import resolve_env
from ldc.domain.models import WorkspaceConfig
from ldc.ports.reporter import IReporter


class EnvCommand:

    def __init__(self, reporter: IReporter) -> None:
        self._reporter = reporter

    def execute(
        self,
        config: WorkspaceConfig,
        service_name: str,
        config_dir: str = ".",
        show_inherited: bool = False,
        filter_prefix: Optional[str] = None,
    ) -> None:
        svc = config.services.get(service_name)
        if svc is None:
            self._reporter.error(f"Unknown service '{service_name}'")
            return

        resolved = resolve_env(svc.env, svc.env_files, config_dir)

        system_keys = set(os.environ.keys())

        rows = []
        for key, value in sorted(resolved.items()):
            if filter_prefix and not key.upper().startswith(filter_prefix.upper()):
                continue
            if not show_inherited and key in system_keys and key not in svc.env:
                env_file_keys = self._collect_env_file_keys(svc.env_files, config_dir)
                if key not in env_file_keys:
                    continue
            source = self._source(key, svc.env, svc.env_files, config_dir, system_keys)
            rows.append((key, value, source))

        self._print(service_name, rows, svc.env_files, config_dir)

    def _source(self, key, inline_env, env_files, base_dir, system_keys):
        if key in inline_env:
            return "inline"
        from ldc.application.env_resolver import _parse_env_file
        from pathlib import Path
        for path in reversed(env_files):
            p = Path(path) if Path(path).is_absolute() else Path(base_dir) / path
            if p.exists() and key in _parse_env_file(p):
                return p.name
        if key in system_keys:
            return "system"
        return "?"

    def _collect_env_file_keys(self, env_files, base_dir):
        from ldc.application.env_resolver import _parse_env_file
        from pathlib import Path
        keys = set()
        for path in env_files:
            p = Path(path) if Path(path).is_absolute() else Path(base_dir) / path
            if p.exists():
                keys.update(_parse_env_file(p).keys())
        return keys

    def _print(self, service_name, rows, env_files, config_dir):
        try:
            from rich.console import Console
            from rich.table import Table
            from rich import box
            console = Console()
            table = Table(title=f"Env: {service_name}", box=box.ROUNDED, show_header=True)
            table.add_column("Variable", min_width=30)
            table.add_column("Value", min_width=40)
            table.add_column("Source", style="dim")
            for key, value, source in rows:
                table.add_row(key, value, source)
            console.print(table)
        except ImportError:
            print(f"\n=== {service_name} environment ===")
            for key, value, source in rows:
                print(f"{key}={value}  [{source}]")

        if env_files:
            from pathlib import Path
            resolved = [
                str(Path(f) if Path(f).is_absolute() else Path(config_dir) / f)
                for f in env_files
            ]
            print(f"\nenv_files: {', '.join(resolved)}")
