"""
Builds the per-service environment dictionary.

Merge order (later wins):
  1. Inherited system environment (os.environ)
  2. env_file entries  (if configured)
  3. Inline env dict   (from composer.yml service.env)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


def resolve_env(
    service_env: Dict[str, str],
    env_file: "str | None",
    base_dir: str,
) -> Dict[str, str]:
    """
    Build the full environment for a service subprocess.

    Args:
        service_env:  inline env block from the service config
        env_file:     optional path to a .env file (relative to *base_dir*)
        base_dir:     service working directory (used to resolve relative env_file)
    """
    merged = dict(os.environ)  # start with current process environment

    if env_file:
        file_path = Path(base_dir) / env_file if not Path(env_file).is_absolute() else Path(env_file)
        if file_path.exists():
            merged.update(_parse_env_file(file_path))

    merged.update(service_env)  # inline env wins over file

    return merged


def _parse_env_file(path: Path) -> Dict[str, str]:
    """
    Parse a simple .env file.

    Supports:
      KEY=value
      KEY="quoted value"
      # comments
      export KEY=value
    """
    result: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        result[key] = value
    return result
