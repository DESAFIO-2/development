"""Recuperador Híbrido: Casamento Tabular DCB, TF-IDF e BM25 com Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

from app.application.ports import RetrieverPort
from app.retrieval.lexical_retrievers import BM25Retriever, TFIDFRetriever
from app.retrieval.schemas import NormativeChunkDTO, RetrievalHitDTO
from app.retrieval.tabular_matcher import CanonicalMedicationItem, TabularDCBMatcher
from app.retrieval.text_normalizer import normalizar_texto_pt


class HybridRetriever(RetrieverPort):
    """Orquestra a busca híbrida de alta precisão com calibração científica de abstenção."""

    _SISREG_DOMAIN_TOKENS: frozenset[str] = frozenset(
        {
            "sisreg",
            "regulacao",
            "cppas",
            "ecocardiograma",
            "cardiologia",
            "endoscopia",
            "ressonancia",
            "reumatologia",
            "endocrinologia",
            "exame",
            "consulta",
        }
    )

    def __init__(
        self,
        medications: list[CanonicalMedicationItem],
        chunks: list[NormativeChunkDTO],
        rrf_k: int = 60,
    ) -> None:
        self.medications = medications
        self.chunks = {c.chunk_id: c for c in chunks}
        self.tabular = TabularDCBMatcher(medications)
        self.tfidf = TFIDFRetriever(chunks)
        self.bm25 = BM25Retriever(chunks)
        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.18,
    ) -> list[RetrievalHitDTO]:
        """Executa busca híbrida ponderada garantindo abstenção em casos fora de catálogo."""
        med_matches = self.tabular.casar(query)
        matched_dcbs = {med.dcb_name: score for score, med in med_matches}

        norm_query_tokens = set(normalizar_texto_pt(query).split())
        is_sisreg_intent = bool(norm_query_tokens.intersection(self._SISREG_DOMAIN_TOKENS))

        tfidf_hits = self.tfidf.search(query, top_k=len(self.chunks), min_score=0.01)
        bm25_hits = self.bm25.search(query, top_k=len(self.chunks), min_score=0.01)

        tfidf_ranks = {hit.chunk_id: rank + 1 for rank, hit in enumerate(tfidf_hits)}
        tfidf_scores = {hit.chunk_id: hit.score for hit in tfidf_hits}

        bm25_ranks = {hit.chunk_id: rank + 1 for rank, hit in enumerate(bm25_hits)}
        bm25_scores = {hit.chunk_id: hit.score for hit in bm25_hits}

        resultados: list[RetrievalHitDTO] = []
        for chunk_id, chunk in self.chunks.items():
            t_score = tfidf_scores.get(chunk_id, 0.0)
            b_score = bm25_scores.get(chunk_id, 0.0)

            rrf_comp = 0.0
            if chunk_id in tfidf_ranks:
                rrf_comp += (self.rrf_k + 1.0) / (self.rrf_k + tfidf_ranks[chunk_id])
            if chunk_id in bm25_ranks:
                rrf_comp += (self.rrf_k + 1.0) / (self.rrf_k + bm25_ranks[chunk_id])
            rrf_norm = rrf_comp / 2.0

            lexical_score = 0.55 * t_score + 0.45 * b_score

            chunk_dcb_boost = 0.0
            best_dcb: str | None = None
            for dcb_name in chunk.dcb_mentions:
                if dcb_name in matched_dcbs:
                    if matched_dcbs[dcb_name] > chunk_dcb_boost:
                        chunk_dcb_boost = matched_dcbs[dcb_name]
                        best_dcb = dcb_name

            if chunk_dcb_boost > 0.0:
                final_score = 0.50 * lexical_score + 0.35 * chunk_dcb_boost + 0.15 * rrf_norm
            elif is_sisreg_intent and chunk.route_category == "SISREG_EXAME_CONSULTA":
                final_score = 0.80 * lexical_score + 0.20 * rrf_norm
            elif matched_dcbs:
                final_score = 0.35 * lexical_score
            else:
                final_score = 0.30 * lexical_score

            if final_score >= min_score:
                resultados.append(
                    RetrievalHitDTO(
                        chunk_id=chunk.chunk_id,
                        score=round(final_score, 4),
                        source_id=chunk.source_id,
                        document_title=chunk.document_title,
                        section=chunk.section,
                        page_number=chunk.page_number,
                        route_category=chunk.route_category,
                        text=chunk.text,
                        matched_dcb=best_dcb,
                        retriever_name="hybrid_dcb_rrf",
                    )
                )

        resultados.sort(key=lambda item: item.score, reverse=True)
        return resultados[:top_k]
