"""Repositório de chunks literais de evidência aprovada (one-evidence-v2: 2.114 chunks)."""

from __future__ import annotations

import json
from pathlib import Path

from app.application.ports import EvidenceChunkDTO, EvidenceRepositoryPort
from app.core.config import settings


class LocalEvidenceChunkRepository(EvidenceRepositoryPort):
    """Carrega os 2.114 chunks literais verificados (F01, F03 e F04) com índice em memória."""

    def __init__(self, json_path: Path | None = None) -> None:
        path = (
            json_path
            if json_path is not None
            else settings.data_processed_dir / "evidence_chunks_v2.json"
        )
        conteudo = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(conteudo, list) or not conteudo:
            raise ValueError(f"Corpus de evidências precisa conter lista não vazia: {path}")
        self._chunks = [EvidenceChunkDTO.from_dict(item) for item in conteudo]
        for field in ("chunk_id", "evidence_id", "occurrence_id"):
            ids = [getattr(chunk, field) for chunk in self._chunks]
            if any(not value.strip() for value in ids) or len(set(ids)) != len(ids):
                raise ValueError(f"Identificador vazio ou duplicado: {field}")
        for chunk in self._chunks:
            if chunk.page_number < 1 or not chunk.source_url.startswith("https://"):
                raise ValueError(f"Proveniência inválida: {chunk.chunk_id}")
        self._by_chunk_id: dict[str, EvidenceChunkDTO] = {c.chunk_id: c for c in self._chunks}
        self._by_occurrence_id: dict[str, EvidenceChunkDTO] = {
            c.occurrence_id: c for c in self._chunks
        }
        self._by_medicine_id: dict[str, list[EvidenceChunkDTO]] = {}
        for chunk in self._chunks:
            if chunk.medicine_id:
                self._by_medicine_id.setdefault(chunk.medicine_id, []).append(chunk)

    def listar_todos(self) -> list[EvidenceChunkDTO]:
        return list(self._chunks)

    def buscar_por_chunk_id(self, chunk_id: str) -> EvidenceChunkDTO | None:
        return self._by_chunk_id.get(chunk_id)

    def buscar_por_occurrence_ids(
        self, occurrence_ids: list[str] | tuple[str, ...]
    ) -> list[EvidenceChunkDTO]:
        ausentes = set(occurrence_ids) - self._by_occurrence_id.keys()
        if ausentes:
            raise ValueError(f"Ocorrências sem evidência: {sorted(ausentes)}")
        return [self._by_occurrence_id[oid] for oid in dict.fromkeys(occurrence_ids)]

    def buscar_por_medicine_id(self, medicine_id: str) -> list[EvidenceChunkDTO]:
        # Namespace med-* da origem; não aceita medication_id canônico MED-* como join.
        return list(self._by_medicine_id.get(medicine_id, []))
