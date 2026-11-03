import time
from collections.abc import Generator
from contextlib import contextmanager

from app.core.config import settings


@contextmanager
def trace_operation(operation_name: str) -> Generator[None, None, None]:
    """Context manager leve para medição de latência e instrumentação de etapas do RAG."""
    start_time = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if settings.environment in ("development", "local"):
            _ = elapsed_ms
