"""Adaptador concreto para o banco vetorial ChromaDB (Multi-Coleções).

Gerencia as 4 coleções persistentes do SUS Cidadão:
1. `ceaf_live_stock`: Estoque em tempo real do Alto Custo (Asa Sul, Ceilândia, Gama).
2. `df_pharmacies`: Farmácias geolocalizadas do Distrito Federal.
3. `sus_normative_protocols`: Portarias oficiais (RENAME 2024, Farmácia Popular, REME-DF, SISREG).
4. `sus_unified_pdf_corpus`: Corpus documental unificado em PDF.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings


@dataclass(frozen=True)
class SemanticHit:
    """Resultado individual de consulta semântica vetorial."""

    id: str
    document: str
    metadata: dict[str, Any]
    distance: float
    relevance_score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ChromaVectorStoreAdapter:
    """Adaptador de persistência e consulta multi-coleção no ChromaDB."""

    COLLECTION_STOCK = "ceaf_live_stock"
    COLLECTION_PHARMACIES = "df_pharmacies"
    COLLECTION_PROTOCOLS = "sus_normative_protocols"
    COLLECTION_UNIFIED_PDF_CORPUS = "sus_unified_pdf_corpus"

    def __init__(self, vectorstore_dir: Path | None = None) -> None:
        if vectorstore_dir is not None:
            self.vectorstore_dir = vectorstore_dir
        else:
            self.vectorstore_dir = settings.vector_store_path

        self.vectorstore_dir.mkdir(parents=True, exist_ok=True)
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import importlib

                chromadb = importlib.import_module("chromadb")
                chroma_config = importlib.import_module("chromadb.config")

                self._client = chromadb.PersistentClient(
                    path=str(self.vectorstore_dir),
                    settings=chroma_config.Settings(anonymized_telemetry=False),
                )
            except (ImportError, Exception):
                return None
        return self._client

    def _get_or_create_collection(self, name: str) -> Any:
        client = self._get_client()
        if client is None:
            return None
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def search_semantic(
        self,
        query: str,
        collection_name: str,
        where_filter: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[SemanticHit]:
        """Consulta semântica por similaridade de cosseno com suporte a filtros de metadados."""
        col = self._get_or_create_collection(collection_name)
        if col is None:
            return []

        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": top_k,
        }
        if where_filter:
            kwargs["where"] = where_filter

        results = col.query(**kwargs)

        hits: list[SemanticHit] = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i in range(len(ids)):
            dist = float(distances[i]) if i < len(distances) else 1.0
            relevance = max(0.0, min(1.0, 1.0 - dist))
            hits.append(
                SemanticHit(
                    id=ids[i],
                    document=documents[i] if i < len(documents) else "",
                    metadata=metadatas[i] if i < len(metadatas) else {},
                    distance=round(dist, 4),
                    relevance_score=round(relevance, 4),
                )
            )

        hits.sort(key=lambda h: h.relevance_score, reverse=True)
        return hits

    def index_ceaf_stock(self, stock_json_path: Path) -> int:
        """Textualiza e indexa o estoque em tempo real das Farmácias de Alto Custo (CEAF)."""
        if not stock_json_path.exists():
            return 0
        data = json.loads(stock_json_path.read_text(encoding="utf-8"))
        items = data.get("items", [])
        if not items:
            return 0

        col = self._get_or_create_collection(self.COLLECTION_STOCK)
        if col is None:
            return 0

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for item in items:
            cod = str(item["cod_produto"]).strip()
            desc = str(item["desc_produto"]).strip()
            unidade = str(item["unidade"]).strip()
            disp = str(item["disp_estoque"]).strip()
            origem = str(item.get("origem_abastecimento", "SES-DF")).strip()
            psico = str(item.get("psicotropico", "Outros")).strip()
            att = str(item.get("ultima_atualizacao", "")).strip()

            doc_id = f"ESTOQUE_{unidade.upper().replace(' ', '_')}_{cod}"
            doc_text = (
                f"Medicamento de Alto Custo: {desc} (Código: {cod}). "
                f"Unidade de Dispensação: Farmácia de Alto Custo de {unidade} (CEAF-DF). "
                f"Disponibilidade em Estoque: {disp}. "
                f"Origem do Abastecimento: {origem}. Classificação: {psico}. "
                f"Última atualização registrada: {att}."
            )
            ids.append(doc_id)
            documents.append(doc_text)
            metadatas.append(
                {
                    "cod_produto": cod,
                    "unidade": unidade,
                    "disp_estoque": disp,
                    "tem_estoque": "COM ESTOQUE" in disp.upper(),
                    "origem": origem,
                }
            )

        col.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(ids)
