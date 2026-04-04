"""Application service: runs install commands via subprocess."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict

from ldc.domain.models import InstallConfig
from ldc.ports.installer import IInstaller


class SubprocessInstaller(IInstaller):

    def install(
        self,
        service_name: str,
        config: InstallConfig,
        working_dir: str,
        env: Dict[str, str],
        log_file: str,
    ) -> None:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(f"\n[LDC] Installing '{service_name}': {config.command}\n")
            fh.flush()

            result = subprocess.run(
                config.command,
                shell=True,
                cwd=working_dir,
                env=env,
                stdout=fh,
                stderr=fh,
            )

        if result.returncode != 0:
            raise RuntimeError(
                f"Install command failed for '{service_name}' "
                f"(exit {result.returncode}). Check log: {log_file}"
            )
