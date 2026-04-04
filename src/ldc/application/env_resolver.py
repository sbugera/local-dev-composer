"""
Builds the per-service environment dictionary.

Merge order (later wins):
  1. Inherited system environment (os.environ)
  2. env_files entries, in listed order (each overrides the previous)
  3. Inline env dict (from composer.yml service.env)

env_files are resolved relative to config_dir (where composer.yml lives),
not relative to the service working directory.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List


def resolve_env(
    service_env: Dict[str, str],
    env_files: List[str],
    config_dir: str = ".",
) -> Dict[str, str]:
    merged = dict(os.environ)

    for env_file in env_files:
        file_path = Path(env_file) if Path(env_file).is_absolute() else Path(config_dir) / env_file
        if file_path.exists():
            merged.update(_parse_env_file(file_path))

    merged.update(service_env)

    return merged


def _parse_env_file(path: Path) -> Dict[str, str]:
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
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        result[key] = value
    return result
