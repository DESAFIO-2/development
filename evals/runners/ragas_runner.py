"""Benchmark determinístico de recuperação e auditoria no Golden Dataset.

Avalia o sistema contra o conjunto padrão-ouro (`evals/datasets/golden_set_v1.jsonl` ou
`evals/datasets/golden_set_v2_consolidado.jsonl`), calculando métricas de Recuperação de
Informação (IR), acurácia de roteamento de gratuidade, abstenção, taxa de aprovação de
guardrails éticos e registrando linhagem criptográfica SHA-256 via `MLflowExperimentTracker`.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "backend"))

from observability.mlflow_tracker import MLflowExperimentTracker  # noqa: E402

from app.application.use_cases.audit_prescription import (  # noqa: E402
    AuditPrescriptionUseCase,
)
from app.domain.prescription import (  # noqa: E402
    MedicationItemInput,
    PrescriptionAuditRequest,
)
from app.infrastructure.persistence.repositories.canonical_medication_repository import (  # noqa: E402
    LocalCanonicalMedicationRepository,
)
from app.infrastructure.persistence.repositories.normative_chunk_repository import (  # noqa: E402
    LocalNormativeChunkRepository,
)
from app.retrieval.hybrid_retriever import HybridRetriever  # noqa: E402

DATASET_GOLDEN = RAIZ / "evals" / "datasets" / "golden_set_v1.jsonl"
PASTA_RELATORIOS = RAIZ / "evals" / "reports"


@dataclass(frozen=True)
class BenchmarkMetrics:
    """Métricas consolidadas de avaliação do RAG no Golden Dataset."""

    total_casos: int
    hit_rate_at_3: float
    recall_at_3: float
    mrr: float
    acuracia_roteamento: float
    taxa_bloqueio_clinico: float
    acuracia_abstencao: float
    sucesso_geral: bool
    falhas: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def executar_benchmark(caminho_dataset: Path = DATASET_GOLDEN) -> BenchmarkMetrics:
    med_repo = LocalCanonicalMedicationRepository(
        RAIZ / "data" / "processed" / "medicamentos_sus_canonical.json"
    )
    chunk_repo = LocalNormativeChunkRepository(
        RAIZ / "data" / "processed" / "normative_chunks.json"
    )
    retriever = HybridRetriever(med_repo.listar_todos(), chunk_repo.listar_todos())
    use_case = AuditPrescriptionUseCase(medication_repo=med_repo, retriever=retriever)

    with caminho_dataset.open(encoding="utf-8") as f:
        casos = [json.loads(linha) for linha in f if linha.strip()]

    if not casos:
        raise ValueError(f"Dataset sem casos: {caminho_dataset}")

    falhas: dict[str, list[str]] = {}
    hits_count = 0
    total_recall = 0.0
    reciprocal_ranks: list[float] = []
    rotas_corretas = 0
    guardrail_corretos = 0
    abstencoes_corretas = 0

    casos_positivos = 0
    casos_clinicos = 0
    casos_abstencao = 0

    for caso in casos:
        query = caso["query"]
        chunks_relevantes = set(caso.get("relevant_chunk_ids", []))
        audit_res = use_case.executar(
            PrescriptionAuditRequest(
                itens=[
                    MedicationItemInput.model_validate(item)
                    for item in caso.get("audit_items", [{"nome_digitado": query}])
                ],
                pergunta_adicional=query,
            )
        )
        erros = []

        if caso.get("is_clinical_block", False):
            casos_clinicos += 1
            if audit_res.solicitou_automedicacao and not audit_res.itens_auditados:
                guardrail_corretos += 1
            else:
                falhas[caso["id"]] = ["bloqueio_clinico"]
            continue

        retrieved_ids = [hit.chunk_id for hit in retriever.search(query, top_k=3)]
        rota_obtida = (
            audit_res.itens_auditados[0].via_retirada.value if audit_res.itens_auditados else None
        )
        if caso.get("should_abstain", False):
            casos_abstencao += 1
            if not retrieved_ids and rota_obtida == "NAO_PADRONIZADO":
                abstencoes_corretas += 1
            else:
                falhas[caso["id"]] = ["abstencao"]
            continue

        casos_positivos += 1
        if not chunks_relevantes:
            raise ValueError(f"{caso['id']}: caso positivo sem chunks relevantes")

        intersect = chunks_relevantes.intersection(retrieved_ids)
        hits_count += bool(intersect)
        total_recall += len(intersect) / len(chunks_relevantes)
        rank = next(
            (i for i, chunk_id in enumerate(retrieved_ids, 1) if chunk_id in chunks_relevantes),
            0,
        )
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)
        if intersect != chunks_relevantes or rank != 1:
            erros.append("recuperacao")

        rotas = {
            "UBS_ATENCAO_PRIMARIA": "UBS_REME_DF",
            "ALTO_CUSTO_CEAF": "FARMACIA_ALTO_CUSTO",
        }
        rota_esperada = rotas.get(caso["expected_route"], caso["expected_route"])
        if audit_res.itens_auditados and all(
            item.via_retirada.value == rota_esperada for item in audit_res.itens_auditados
        ):
            rotas_corretas += 1
        else:
            erros.append(f"roteamento esperado {rota_esperada}, obtido {rota_obtida}")
        if erros:
            falhas[caso["id"]] = erros

    if not (casos_positivos and casos_clinicos and casos_abstencao):
        raise ValueError("O benchmark exige casos positivos, clínicos e de abstenção.")

    hit_rate = hits_count / casos_positivos if casos_positivos else 1.0
    recall = total_recall / casos_positivos if casos_positivos else 1.0
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 1.0
    route_acc = rotas_corretas / casos_positivos if casos_positivos else 1.0
    guardrail_acc = guardrail_corretos / casos_clinicos if casos_clinicos else 1.0
    abstention_acc = abstencoes_corretas / casos_abstencao if casos_abstencao else 1.0

    sucesso = not falhas

    return BenchmarkMetrics(
        total_casos=len(casos),
        hit_rate_at_3=round(hit_rate, 4),
        recall_at_3=round(recall, 4),
        mrr=round(mrr, 4),
        acuracia_roteamento=round(route_acc, 4),
        taxa_bloqueio_clinico=round(guardrail_acc, 4),
        acuracia_abstencao=round(abstention_acc, 4),
        sucesso_geral=sucesso,
        falhas=falhas,
    )


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        with contextlib.suppress(AttributeError, io.UnsupportedOperation):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_GOLDEN,
        help="Caminho do dataset JSONL a avaliar (padrão: evals/datasets/golden_set_v1.jsonl)",
    )
    args = parser.parse_args()
    caminho_dataset: Path = args.dataset if args.dataset.is_absolute() else (RAIZ / args.dataset)

    print("=" * 80)
    print(f"  BENCHMARK CIENTÍFICO RAG — DATASET: {caminho_dataset.name}")
    print("=" * 80)

    metricas = executar_benchmark(caminho_dataset)

    tracker = MLflowExperimentTracker(raiz_repo=RAIZ)
    run_record = tracker.registrar_execucao(
        run_name=f"rag_hybrid_{caminho_dataset.stem}",
        params={
            "retriever_type": "hybrid_dcb_tfidf_bm25_rrf",
            "rrf_k": 60,
            "min_score": 0.18,
            "top_k": 3,
            "dataset": caminho_dataset.name,
            "total_casos": metricas.total_casos,
        },
        metrics={
            "hit_rate_at_3": metricas.hit_rate_at_3,
            "recall_at_3": metricas.recall_at_3,
            "mrr": metricas.mrr,
            "acuracia_roteamento": metricas.acuracia_roteamento,
            "taxa_bloqueio_clinico": metricas.taxa_bloqueio_clinico,
            "acuracia_abstencao": metricas.acuracia_abstencao,
        },
        dataset_path=caminho_dataset,
    )

    print(f"Total de Casos Avaliados:     {metricas.total_casos}")
    print(f"Hit Rate@3:                  {metricas.hit_rate_at_3:.2%}")
    print(f"Recall@3:                    {metricas.recall_at_3:.2%}")
    print(f"Mean Reciprocal Rank (MRR):  {metricas.mrr:.4f}")
    print(f"Acurácia de Roteamento:      {metricas.acuracia_roteamento:.2%}")
    print(f"Taxa Bloqueio Clínico:       {metricas.taxa_bloqueio_clinico:.2%}")
    print(f"Acurácia de Abstenção:       {metricas.acuracia_abstencao:.2%}")
    print(f"MLflow Run ID:               {run_record.run_id}")
    print(f"Manifest Lineage SHA-256:    {run_record.tags.get('combined_sha256', '')[:16]}...")

    PASTA_RELATORIOS.mkdir(exist_ok=True)
    relatorio = {
        "executado_em": datetime.now(UTC).isoformat(),
        "dataset": caminho_dataset.name,
        "mlflow_run_id": run_record.run_id,
        "manifest_combined_sha256": run_record.tags.get("combined_sha256", ""),
        **metricas.to_dict(),
    }
    destino = PASTA_RELATORIOS / f"rag_benchmark_{caminho_dataset.stem}.json"
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRelatório salvo em: {destino.relative_to(RAIZ)}")

    if not metricas.sucesso_geral:
        for caso_id, falhas in metricas.falhas.items():
            print(f"{caso_id}: {', '.join(falhas)}")
        print("[ERRO] Reprovado: métricas abaixo dos limiares de aceitação.")
        return 1

    print("[OK] APROVADO: Sistema atende a todos os critérios de qualidade.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
