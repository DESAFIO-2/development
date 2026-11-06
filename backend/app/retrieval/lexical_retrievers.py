"""Recuperadores lexicais determinísticos: TF-IDF (baseline ADR-003) e Okapi BM25."""

from __future__ import annotations

import math
from collections import Counter

from app.retrieval.schemas import NormativeChunkDTO, RetrievalHitDTO
from app.retrieval.text_normalizer import tokenizar_com_ngrams


class TFIDFRetriever:
    """Recuperador vetorial esparso por cosseno TF-IDF com sublinear term-frequency."""

    def __init__(self, chunks: list[NormativeChunkDTO], max_ngram: int = 2) -> None:
        self.chunks = chunks
        self.max_ngram = max_ngram
        self.idf: dict[str, float] = {}
        self.doc_vectors: list[dict[str, float]] = []
        self._build_index()

    def _build_index(self) -> None:
        n_docs = len(self.chunks)
        if n_docs == 0:
            return

        doc_tokens_list: list[list[str]] = []
        df_counter: Counter[str] = Counter()

        for chunk in self.chunks:
            composite_text = (
                f"{chunk.document_title} {chunk.section} {chunk.text} "
                f"{' '.join(chunk.dcb_mentions)}"
            )
            tokens = tokenizar_com_ngrams(composite_text, self.max_ngram)
            doc_tokens_list.append(tokens)
            for unique_tok in set(tokens):
                df_counter[unique_tok] += 1

        self.idf = {
            term: math.log((1.0 + n_docs) / (1.0 + df)) + 1.0 for term, df in df_counter.items()
        }

        for tokens in doc_tokens_list:
            vec = self._vectorize(tokens)
            self.doc_vectors.append(vec)

    def _vectorize(self, tokens: list[str]) -> dict[str, float]:
        tf_counts = Counter(tokens)
        raw_weights: dict[str, float] = {}
        for term, count in tf_counts.items():
            if term in self.idf:
                sublinear_tf = 1.0 + math.log(count)
                raw_weights[term] = sublinear_tf * self.idf[term]
        norm = math.sqrt(sum(w * w for w in raw_weights.values()))
        if norm == 0.0:
            return {}
        return {term: weight / norm for term, weight in raw_weights.items()}

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.12,
    ) -> list[RetrievalHitDTO]:
        """Consulta por similaridade de cosseno com corte por min_score."""
        q_tokens = tokenizar_com_ngrams(query, self.max_ngram)
        q_vec = self._vectorize(q_tokens)
        if not q_vec:
            return []

        scored: list[tuple[float, NormativeChunkDTO]] = []
        for chunk, d_vec in zip(self.chunks, self.doc_vectors, strict=True):
            dot = sum(q_weight * d_vec.get(term, 0.0) for term, q_weight in q_vec.items())
            if dot >= min_score:
                scored.append((dot, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievalHitDTO(
                chunk_id=chunk.chunk_id,
                score=round(score, 4),
                source_id=chunk.source_id,
                document_title=chunk.document_title,
                section=chunk.section,
                page_number=chunk.page_number,
                route_category=chunk.route_category,
                text=chunk.text,
                matched_dcb=None,
                retriever_name="tfidf_baseline",
            )
            for score, chunk in scored[:top_k]
        ]


class BM25Retriever:
    """Recuperador probabilístico Okapi BM25 normalizado em [0, 1]."""

    def __init__(
        self,
        chunks: list[NormativeChunkDTO],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.doc_freqs: list[Counter[str]] = []
        self.doc_lens: list[int] = []
        self.avgdl: float = 1.0
        self.idf: dict[str, float] = {}
        self._build_index()

    def _build_index(self) -> None:
        n_docs = len(self.chunks)
        if n_docs == 0:
            return

        df_counter: Counter[str] = Counter()
        for chunk in self.chunks:
            composite_text = (
                f"{chunk.document_title} {chunk.section} {chunk.text} "
                f"{' '.join(chunk.dcb_mentions)}"
            )
            tokens = tokenizar_com_ngrams(composite_text, max_ngram=1)
            counts = Counter(tokens)
            self.doc_freqs.append(counts)
            self.doc_lens.append(len(tokens))
            for tok in counts:
                df_counter[tok] += 1

        self.avgdl = sum(self.doc_lens) / n_docs if n_docs else 1.0
        self.idf = {
            term: math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
            for term, df in df_counter.items()
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.15,
    ) -> list[RetrievalHitDTO]:
        """Consulta BM25 com escore normalizado em [0, 1] via s / (s + 4)."""
        q_tokens = tokenizar_com_ngrams(query, max_ngram=1)
        if not q_tokens:
            return []

        scored: list[tuple[float, NormativeChunkDTO]] = []
        for chunk, tf_map, doc_len in zip(self.chunks, self.doc_freqs, self.doc_lens, strict=True):
            raw_bm25 = 0.0
            for term in set(q_tokens):
                if term not in tf_map:
                    continue
                tf = tf_map[term]
                idf = self.idf.get(term, 0.0)
                denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                raw_bm25 += idf * ((tf * (self.k1 + 1.0)) / denom)

            norm_score = raw_bm25 / (raw_bm25 + 4.0) if raw_bm25 > 0 else 0.0
            if norm_score >= min_score:
                scored.append((norm_score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievalHitDTO(
                chunk_id=chunk.chunk_id,
                score=round(score, 4),
                source_id=chunk.source_id,
                document_title=chunk.document_title,
                section=chunk.section,
                page_number=chunk.page_number,
                route_category=chunk.route_category,
                text=chunk.text,
                matched_dcb=None,
                retriever_name="bm25_lexical",
            )
            for score, chunk in scored[:top_k]
        ]
