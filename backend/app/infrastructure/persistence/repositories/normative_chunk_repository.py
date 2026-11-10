"""Repositório de chunks normativos de portarias oficiais do SUS (Silver Layer)."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.retrieval.schemas import NormativeChunkDTO


class LocalNormativeChunkRepository:
    """Carrega os fragmentos de portarias das camadas processed para o Hybrid Retriever."""

    def __init__(self, json_path: Path | None = None) -> None:
        path = (
            json_path
            if json_path is not None
            else settings.data_processed_dir / "normative_chunks.json"
        )
        conteudo = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(conteudo, list) or not conteudo:
            raise ValueError(f"Corpus precisa conter uma lista não vazia: {path}")
        self._chunks = [NormativeChunkDTO.from_dict(item) for item in conteudo]

    def listar_todos(self) -> list[NormativeChunkDTO]:
        return list(self._chunks)
