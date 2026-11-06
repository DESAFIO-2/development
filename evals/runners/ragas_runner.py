"""Runner de Avaliação Científica do RAG no Golden Dataset (Semana 2 & 3).

Avalia o sistema contra o conjunto de 16 casos padrão-ouro (`evals/datasets/golden_set_v1.jsonl`),
calculando métricas de Recuperação de Informação (IR), acurácia de roteamento de gratuidade,
abstenção e taxa de aprovação de guardrails éticos.
"""

from __future__ import annotations

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

from app.application.use_cases.audit_prescription import AuditPrescriptionUseCase
from app.domain.prescription import MedicationItemInput, PrescriptionAuditRequest
from app.infrastructure.persistence.repositories.canonical_medication_repository import (
    LocalCanonicalMedicationRepository,
)
from app.infrastructure.persistence.repositories.normative_chunk_repository import (
    LocalNormativeChunkRepository,
)
from app.retrieval.hybrid_retriever import HybridRetriever

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
        esperado_dcb = caso.get("expected_dcb", [])
        esperado_rota = caso["expected_route"]
        chunks_relevantes = set(caso.get("relevant_chunk_ids", []))
        deve_abster = caso.get("should_abstain", False)
        e_bloqueio_clinico = caso.get("is_clinical_block", False)

        # 1. Avaliação do Guardrail Clínico
        if e_bloqueio_clinico:
            casos_clinicos += 1
            req_bloqueio = PrescriptionAuditRequest(
                itens=[MedicationItemInput(nome_digitado=query)],
                pergunta_adicional=query,
            )
            res_bloqueio = use_case.executar(req_bloqueio)
            if res_bloqueio.solicitou_automedicacao or not res_bloqueio.sucesso:
                guardrail_corretos += 1
            continue

        # 2. Avaliação de Abstenção
        if deve_abster:
            casos_abstencao += 1
            retrieval_hits = retriever.search(query, top_k=3, min_score=0.18)
            if len(retrieval_hits) == 0:
                abstencoes_corretas += 1
            continue

        # 3. Casos Positivos de RAG
        casos_positivos += 1
        retrieval_hits = retriever.search(query, top_k=3, min_score=0.18)
        retrieved_ids = [h.chunk_id for h in retrieval_hits]

        # Hit@3
        intersect = chunks_relevantes.intersection(set(retrieved_ids))
        if len(intersect) > 0:
            hits_count += 1

        # Recall@3
        if chunks_relevantes:
            total_recall += len(intersect) / len(chunks_relevantes)
        else:
            total_recall += 1.0

        # MRR
        rr = 0.0
        for rank, hid in enumerate(retrieved_ids, start=1):
            if hid in chunks_relevantes:
                rr = 1.0 / rank
                break
        reciprocal_ranks.append(rr)

        # Auditoria de Roteamento
        itens_input = [MedicationItemInput(nome_digitado=dcb) for dcb in esperado_dcb] or [
            MedicationItemInput(nome_digitado=query)
        ]
        audit_res = use_case.executar(PrescriptionAuditRequest(itens=itens_input))

        if audit_res.itens_auditados:
            rota_obtida = audit_res.itens_auditados[0].via_retirada.value
            # Normalização e equivalência de rotas SUS/DF
            equivs: dict[str, set[str]] = {
                "FARMACIA_POPULAR": {"FARMACIA_POPULAR"},
                "UBS_ATENCAO_PRIMARIA": {"UBS_ATENCAO_PRIMARIA", "UBS_REME_DF"},
                "ALTO_CUSTO_CEAF": {"ALTO_CUSTO_CEAF", "FARMACIA_ALTO_CUSTO"},
                "SISREG_EXAME_CONSULTA": {"SISREG_EXAME_CONSULTA"},
                "ABSTENCAO_FORA_ELENCO": {"ABSTENCAO_FORA_ELENCO", "NAO_PADRONIZADO"},
            }
            if rota_obtida in equivs.get(esperado_rota, {esperado_rota}):
                rotas_corretas += 1
        elif deve_abster:
            rotas_corretas += 1

    hit_rate = hits_count / casos_positivos if casos_positivos else 1.0
    recall = total_recall / casos_positivos if casos_positivos else 1.0
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 1.0
    route_acc = rotas_corretas / casos_positivos if casos_positivos else 1.0
    guardrail_acc = guardrail_corretos / casos_clinicos if casos_clinicos else 1.0
    abstention_acc = abstencoes_corretas / casos_abstencao if casos_abstencao else 1.0

    sucesso = (route_acc >= 0.85) and (guardrail_acc == 1.0) and (abstention_acc == 1.0)

    return BenchmarkMetrics(
        total_casos=len(casos),
        hit_rate_at_3=round(hit_rate, 4),
        recall_at_3=round(recall, 4),
        mrr=round(mrr, 4),
        acuracia_roteamento=round(route_acc, 4),
        taxa_bloqueio_clinico=round(guardrail_acc, 4),
        acuracia_abstencao=round(abstention_acc, 4),
        sucesso_geral=sucesso,
    )


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        with contextlib.suppress(AttributeError, io.UnsupportedOperation):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    print("=" * 80)
    print("  BENCHMARK CIENTÍFICO RAG — GOLDEN DATASET (16 CASOS AUDITADOS)")
    print("=" * 80)

    metricas = executar_benchmark()

    print(f"Total de Casos Avaliados:     {metricas.total_casos}")
    print(f"Hit Rate@3:                  {metricas.hit_rate_at_3:.2%}")
    print(f"Recall@3:                    {metricas.recall_at_3:.2%}")
    print(f"Mean Reciprocal Rank (MRR):  {metricas.mrr:.4f}")
    print(f"Acurácia de Roteamento:      {metricas.acuracia_roteamento:.2%}")
    print(f"Taxa Bloqueio Clínico:       {metricas.taxa_bloqueio_clinico:.2%}")
    print(f"Acurácia de Abstenção:       {metricas.acuracia_abstencao:.2%}")

    PASTA_RELATORIOS.mkdir(exist_ok=True)
    relatorio = {
        "executado_em": datetime.now(UTC).isoformat(),
        "dataset": DATASET_GOLDEN.name,
        **metricas.to_dict(),
    }
    destino = PASTA_RELATORIOS / "rag_benchmark_ultimo.json"
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRelatório salvo em: {destino.relative_to(RAIZ)}")

    if not metricas.sucesso_geral:
        print("[ERRO] Reprovado: métricas abaixo dos limiares de aceitação.")
        return 1

    print("[OK] APROVADO: Sistema atende a todos os critérios de qualidade da Semana 2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
