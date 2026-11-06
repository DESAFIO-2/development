"""Estruturas de dados e DTOs de recuperação normativa (RAG)."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from app.application.ports import RetrievalHitDTO


def calcular_sha256(texto: str) -> str:
    """Calcula hash SHA-256 determinístico."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class NormativeChunkDTO:
    """Representação de um fragmento de portaria, norma ou protocolo (Silver Layer)."""

    chunk_id: str
    source_id: str
    document_title: str
    section: str
    page_number: int
    text: str
    dcb_mentions: list[str]
    route_category: str
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormativeChunkDTO:
        clean_text = " ".join(str(data["text"]).strip().split())
        return cls(
            chunk_id=str(data["chunk_id"]),
            source_id=str(data["source_id"]),
            document_title=str(data["document_title"]),
            section=str(data["section"]),
            page_number=int(data["page_number"]),
            text=clean_text,
            dcb_mentions=[str(x).lower() for x in data.get("dcb_mentions", [])],
            route_category=str(data["route_category"]),
            sha256=str(data.get("sha256") or calcular_sha256(clean_text)),
        )


__all__ = ["NormativeChunkDTO", "RetrievalHitDTO", "calcular_sha256"]
