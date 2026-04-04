"""Creates and activates a Python virtual environment for a service."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

from ldc.domain.models import VenvConfig


class VenvManager:

    def ensure(self, venv_cfg: VenvConfig, service_dir: str) -> Dict[str, str]:
        """
        Create the venv if it does not exist, then return env vars that
        activate it (prepend Scripts/ to PATH, set VIRTUAL_ENV).
        Merging these into the service env is enough — no command rewriting needed.
        """
        venv_path = Path(venv_cfg.path)
        if not venv_path.is_absolute():
            venv_path = Path(service_dir) / venv_path

        scripts_dir = venv_path / ("Scripts" if sys.platform == "win32" else "bin")
        python_exe = scripts_dir / ("python.exe" if sys.platform == "win32" else "python")

        if not python_exe.exists():
            subprocess.run(
                [venv_cfg.python, "-m", "venv", str(venv_path)],
                check=True,
            )

        current_path = os.environ.get("PATH", "")
        return {
            "VIRTUAL_ENV": str(venv_path),
            "PATH": str(scripts_dir) + os.pathsep + current_path,
            "PYTHONNOUSERSITE": "1",
        }
