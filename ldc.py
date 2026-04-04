#!/usr/bin/env python3
"""
Entry-point shim for running ldc directly without installing.

    python ldc.py <command> [options]

After  pip install -e .  you can simply run:

    ldc <command> [options]
"""
import sys
from pathlib import Path

# Ensure src/ is on sys.path before importing the package
_src = str(Path(__file__).parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from ldc.cli import main  # noqa: E402  (import after path fixup)

if __name__ == "__main__":
    main()
