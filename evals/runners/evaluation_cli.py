"""Execução, retomada e consolidação offline da avaliação oficial."""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from evals.runners.artifacts import (
    atomic_json,
    atomic_text,
    bind_manifest,
    digest,
    read_json,
    source_hashes,
)
from evals.runners.avaliar_ragas_oficial import (
    RAIZ,
    EscoresCasoRagas,
    OfficialRagasCollectionsEvaluator,
    avaliar_coleta_ragas,
    gerar_relatorio_ragas_markdown,
)
from evals.runners.factual_audit import (
    consolidar_auditoria_factual,
    gerar_template_auditoria_factual,
)
from evals.runners.local_preflight import ollama_identity


class CachedEvaluator:
    """Cache por par com histórico de falhas; consolidação não instancia SDKs."""

    def __init__(
        self,
        directory: Path,
        identity: dict[str, Any],
        factory: Callable[[], OfficialRagasCollectionsEvaluator],
        *,
        cache_only: bool = False,
        retry_failed: bool = False,
    ) -> None:
        self.directory = directory
        self.evaluator_provider = "ollama_openai_compat"
        self.evaluator_model = identity["evaluator_model"]
        self.embedding_model = identity["embedding_model"]
        self.factory = factory
        self.delegate: OfficialRagasCollectionsEvaluator | None = None
        self.cache_only = cache_only
        self.retry_failed = retry_failed

    def avaliar_par_positivo(self, **kwargs: Any) -> EscoresCasoRagas:
        path = self.directory / "pares" / f"{digest(kwargs)}.json"
        history: list[dict[str, Any]] = []
        if path.exists():
            saved = read_json(path)
            if saved["input"] != kwargs or digest(saved["attempts"]) != saved["sha256"]:
                raise ValueError("Checkpoint de avaliação corrompido")
            history = saved["attempts"]
            last = history[-1]
            if last.get("scores") is not None:
                return EscoresCasoRagas(**last["scores"])
            if not self.retry_failed or len(history) >= 3:
                raise RuntimeError(last["error"])
        if self.cache_only:
            raise RuntimeError("Avaliação pendente no cache; consolidação não executa inferência")
        if self.delegate is None:
            self.delegate = self.factory()
        start = time.perf_counter()
        attempt: dict[str, Any]
        try:
            score = self.delegate.avaliar_par_positivo(**kwargs)
            attempt = {"scores": asdict(score), "error": None}
        except Exception as exc:
            attempt = {"scores": None, "error": f"{type(exc).__name__}: {exc}"}
        attempt["latency_seconds"] = time.perf_counter() - start
        attempt["timestamp"] = datetime.now(UTC).isoformat()
        history.append(attempt)
        atomic_json(path, {"input": kwargs, "attempts": history, "sha256": digest(history)})
        if attempt["error"]:
            raise RuntimeError(attempt["error"])
        return EscoresCasoRagas(**attempt["scores"])

    def close(self) -> None:
        if self.delegate is not None:
            self.delegate.close()


def codigo_saida(relatorio: dict[str, Any]) -> int:
    if not relatorio["avaliacao_ragas_completa"]:
        return 1
    if not relatorio["auditoria_factual"]["completa"] or relatorio.get("piloto"):
        return 3
    return 0 if relatorio["sucesso_criterios_rag"] else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coleta-dir", type=Path, required=True)
    parser.add_argument("--evaluator-model", default="qwen2.5:14b")
    parser.add_argument("--embedding-model", default="bge-m3")
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--auditoria-humana", type=Path)
    parser.add_argument("--consolidate-only", action="store_true")
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Até 3 tentativas registradas por par; nunca repetir sucessos",
    )
    parser.add_argument(
        "--evaluation-name", default="ragas_v1", help="Novo nome cria reavaliação independente"
    )
    args = parser.parse_args()
    if not args.evaluation_name or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for c in args.evaluation_name
    ):
        parser.error("Nome de avaliação inválido")
    if args.consolidate_only and args.retry_failed:
        parser.error("Consolidação não aceita tentativas de inferência")
    coleta_dir = args.coleta_dir.resolve()
    coleta = read_json(coleta_dir / "resultado.json")
    directory = coleta_dir / args.evaluation_name
    identity = {
        "coleta_sha256": digest(coleta),
        "evaluator_model": args.evaluator_model,
        "embedding_model": args.embedding_model,
        "base_url": args.base_url,
        "timeout": args.timeout,
        "temperature": 0.0,
        "max_tokens": 2048,
        "source_sha256": source_hashes(RAIZ),
    }
    if args.consolidate_only:
        saved = read_json(directory / "manifesto.json")
        if saved["coleta_sha256"] != digest(coleta):
            raise ValueError("Coleta alterada após avaliação")
        identity = saved
    else:
        identity["ollama"] = ollama_identity(
            args.base_url, [args.evaluator_model, args.embedding_model]
        )
        bind_manifest(directory, identity)
    caminho_auditoria = args.auditoria_humana or coleta_dir / "auditoria_factual_humana.json"
    if not caminho_auditoria.exists():
        atomic_json(caminho_auditoria, gerar_template_auditoria_factual(coleta))
    auditoria = read_json(caminho_auditoria)
    consolidar_auditoria_factual(auditoria, coleta)
    avaliador = CachedEvaluator(
        directory,
        identity,
        lambda: OfficialRagasCollectionsEvaluator(
            evaluator_model=args.evaluator_model,
            embedding_model=args.embedding_model,
            base_url=args.base_url,
            metric_cache=directory / "metricas",
            timeout=args.timeout,
        ),
        cache_only=args.consolidate_only,
        retry_failed=args.retry_failed,
    )
    try:
        relatorio = avaliar_coleta_ragas(coleta, avaliador=avaliador, auditoria_factual=auditoria)
    finally:
        avaliador.close()
    relatorio["manifesto_avaliacao"] = identity
    relatorio["tracking_backend"] = "artefatos_json_locais"
    relatorio["avaliacao_id"] = args.evaluation_name
    relatorio["consolidacao_codigo_sha256"] = source_hashes(RAIZ)
    if relatorio.get("piloto"):
        relatorio["status_entregavel"] = "PILOTO_NAO_E_ENTREGA"
    version = directory / "consolidacoes" / uuid4().hex
    atomic_json(version / "avaliacao_ragas.json", relatorio)
    atomic_json(version / "auditoria_factual_humana.json", auditoria)
    markdown = gerar_relatorio_ragas_markdown(relatorio)
    atomic_text(version / "avaliacao_ragas.md", markdown)
    atomic_json(coleta_dir / "avaliacao_ragas.json", relatorio)
    atomic_text(coleta_dir / "avaliacao_ragas.md", markdown)
    print(f"Relatório: {version}; status: {relatorio['status_entregavel']}")
    return codigo_saida(relatorio)
