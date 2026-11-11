"""Adaptadores de geração textual (LLM sem recuperação × LLM com RAG)."""

from app.infrastructure.llm.generator import (
    GeminiRESTGeneratorAdapter,
    OllamaRESTGeneratorAdapter,
    build_generator,
)

__all__ = [
    "GeminiRESTGeneratorAdapter",
    "OllamaRESTGeneratorAdapter",
    "build_generator",
]
