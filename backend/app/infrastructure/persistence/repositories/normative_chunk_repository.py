"""Repositório de chunks normativos de portarias oficiais do SUS (Silver Layer)."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.retrieval.schemas import NormativeChunkDTO


class LocalNormativeChunkRepository:
    """Carrega os fragmentos de portarias das camadas processed para o Hybrid Retriever."""

    def __init__(self, json_path: Path | None = None) -> None:
        if json_path is not None:
            self._path = json_path
        else:
            caminho_config = settings.data_processed_dir / "normative_chunks.json"
            if caminho_config.exists():
                self._path = caminho_config
            else:
                self._path = Path("data/processed/normative_chunks.json")
                if not self._path.exists():
                    self._path = Path("../data/processed/normative_chunks.json")

        self._chunks: list[NormativeChunkDTO] = []
        self._carregar()

    def _carregar(self) -> None:
        if not self._path.exists():
            return
        conteudo = json.loads(self._path.read_text(encoding="utf-8"))
        self._chunks = [NormativeChunkDTO.from_dict(item) for item in conteudo]

    def listar_todos(self) -> list[NormativeChunkDTO]:
        return list(self._chunks)
