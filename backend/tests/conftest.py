"""Configuração global de testes (garante raiz do monorepo, backend no sys.path e spans OTel)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

RAIZ_MONOREPO = Path(__file__).resolve().parents[2]
PASTA_BACKEND = RAIZ_MONOREPO / "backend"

for caminho in (str(RAIZ_MONOREPO), str(PASTA_BACKEND)):
    if caminho not in sys.path:
        sys.path.insert(0, caminho)

# Um provider de verdade, mas que guarda os spans na memória em vez de mandar
# para o Jaeger. O provider global só pode ser definido uma vez por processo.
_exportador = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exportador))
trace.set_tracer_provider(_provider)


@pytest.fixture
def spans() -> InMemorySpanExporter:
    _exportador.clear()
    return _exportador
