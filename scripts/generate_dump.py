#!/usr/bin/env python3
"""Ponto de entrada de compatibilidade para gerar o dump do projeto.

Executa o script de consolidação do código-fonte em dump_projeto.txt.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from scripts.dump_project import main
except ImportError:
    from dump_project import main  # type: ignore

if __name__ == "__main__":
    sys.exit(main())

