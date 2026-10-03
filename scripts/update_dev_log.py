#!/usr/bin/env python3
"""Ponto de entrada alternativo/atalho para scripts/generate_dev_log.py."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from scripts.generate_dev_log import main
except ImportError:
    from generate_dev_log import main  # type: ignore

if __name__ == "__main__":
    sys.exit(main())

