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
sys.path.insert(0, str(Path(__file__).parent / "src"))

from ldc.cli import main  # noqa: E402  (import after path fixup)

if __name__ == "__main__":
    main()
