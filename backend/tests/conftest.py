"""Configuração global de testes (garante raiz do monorepo e backend no sys.path)."""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ_MONOREPO = Path(__file__).resolve().parents[2]
PASTA_BACKEND = RAIZ_MONOREPO / "backend"

for caminho in (str(RAIZ_MONOREPO), str(PASTA_BACKEND)):
    if caminho not in sys.path:
        sys.path.insert(0, caminho)
