"""Adaptadores de geração textual (LLM sem recuperação × LLM com RAG)."""

from app.infrastructure.llm.generator import (
    DeterministicPairedGeneratorAdapter,
    GeminiRESTGeneratorAdapter,
    OllamaRESTGeneratorAdapter,
    build_generator,
)

__all__ = [
    "DeterministicPairedGeneratorAdapter",
    "GeminiRESTGeneratorAdapter",
    "OllamaRESTGeneratorAdapter",
    "build_generator",
]
