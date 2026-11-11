import logging
import time
from collections.abc import Generator
from contextlib import contextmanager

from opentelemetry import trace

logger = logging.getLogger("app.telemetria")
tracer = trace.get_tracer("app.telemetria")


@contextmanager
def trace_operation(operation_name: str) -> Generator[None, None, None]:
    """Mede uma etapa (ex.: "retrieval", "llm") como span do trace e registra no log."""
    inicio = time.perf_counter()
    with tracer.start_as_current_span(operation_name):
        try:
            yield
        finally:
            logger.info(
                "operacao concluida",
                extra={
                    "operacao": operation_name,
                    "duracao_ms": round((time.perf_counter() - inicio) * 1000, 2),
                },
            )
