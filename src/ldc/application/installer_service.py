"""Application service: runs install commands via subprocess."""
from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

# On Windows, CREATE_NO_WINDOW prevents child processes from writing to the
# terminal via the Windows Console API, which would corrupt the display even
# when stdout/stderr are redirected to a log file.
from ldc.domain.models import InstallConfig
from ldc.ports.installer import IInstaller

# On Windows, CREATE_NO_WINDOW prevents child processes from writing to the
# terminal via the Windows Console API, which would corrupt the display even
# when stdout/stderr are redirected to a log file.
_EXTRA_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


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

        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()

        with open(log_file, "a", encoding="utf-8") as fh:
            fh.write(f"\n{'='*60}\n")
            fh.write(f"[LDC] Installing '{service_name}' at {started_at.isoformat()}\n")
            fh.write(f"[LDC] Command: {config.command}\n")
            fh.write(f"{'='*60}\n")
            fh.flush()

            try:
                result = subprocess.run(
                    config.command,
                    shell=True,
                    cwd=working_dir,
                    env=env,
                    stdout=fh,
                    stderr=fh,
                    creationflags=_EXTRA_FLAGS,
                )
                returncode = result.returncode
                status = "SUCCESS" if returncode == 0 else f"FAILED (exit {returncode})"
            except BaseException as exc:
                status = f"ERROR ({type(exc).__name__}: {exc})"
                raise
            finally:
                finished_at = datetime.now(timezone.utc)
                elapsed = time.monotonic() - t0
                fh.write(f"\n{'='*60}\n")
                fh.write(f"[LDC] Finished '{service_name}' at {finished_at.isoformat()}\n")
                fh.write(f"[LDC] Status: {status} — elapsed {elapsed:.1f}s\n")
                fh.write(f"{'='*60}\n")
                fh.flush()

        if returncode != 0:
            raise RuntimeError(
                f"Install command failed for '{service_name}' "
                f"(exit {returncode}). Check log: {log_file}"
            )
