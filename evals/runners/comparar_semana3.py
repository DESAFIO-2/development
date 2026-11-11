"""Coleta pareada auditável. Diagnósticos locais não substituem RAGAS nem revisão factual."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "backend"))

from observability.mlflow_tracker import MLflowExperimentTracker  # noqa: E402

from app.application.ports import GenerationResultDTO, GeneratorPort, RetrievalHitDTO, RetrieverPort  # noqa: E402
from app.infrastructure.llm import build_generator  # noqa: E402
from app.infrastructure.llm.generator import PROMPT_VERSION, SYSTEM_PROMPT  # noqa: E402
from app.infrastructure.persistence.repositories.canonical_medication_repository import (  # noqa: E402
    LocalCanonicalMedicationRepository,
)
from app.infrastructure.persistence.repositories.normative_chunk_repository import (  # noqa: E402
    LocalNormativeChunkRepository,
)
from app.retrieval.hybrid_retriever import HybridRetriever  # noqa: E402
from app.retrieval.text_normalizer import tokenizar_com_ngrams  # noqa: E402

DATASET_PADRAO = RAIZ / "evals/datasets/golden_set_v2_consolidado.jsonl"
Gerador = GeneratorPort | Callable[[str, tuple[RetrievalHitDTO, ...]], str]


@dataclass(frozen=True)
class RespostaExperimental:
    caso_id: str
    variante: str
    pergunta: str
    referencia: str
    resposta: str
    evidencias: tuple[RetrievalHitDTO, ...]
    geracao: GenerationResultDTO


def comparar_caso(
    *,
    caso_id: str,
    pergunta: str,
    referencia: str,
    gerar: Gerador,
    retriever: RetrieverPort,
    top_k: int = 3,
) -> tuple[RespostaExperimental, RespostaExperimental]:
    if top_k < 1:
        raise ValueError("top_k deve ser positivo")
    evidencias = tuple(retriever.search(pergunta, top_k=top_k))

    def executar(rag: bool) -> RespostaExperimental:
        contexto = evidencias if rag else ()
        if isinstance(gerar, GeneratorPort):
            result = gerar.generate(pergunta, contexto, rag_mode=rag)
        else:
            inicio = time.perf_counter()
            result = GenerationResultDTO(
                gerar(pergunta, contexto),
                "callable",
                "nao_identificado",
                rag,
                (time.perf_counter() - inicio) * 1000,
                execution_kind="synthetic",
            )
        return RespostaExperimental(
            caso_id,
            "llm_com_rag" if rag else "llm_sem_recuperacao",
            pergunta,
            referencia,
            result.text,
            contexto,
            result,
        )

    return executar(False), executar(True)


def _detectar_rota_na_resposta(texto: str) -> str:
    """Classifica a rota administrativa predominante indicada na resposta gerada."""
    lower = texto.lower()

    if (
        "bloqueio ético e clínico" in lower
        or "alerta de emergência" in lower
        or "preservação do ato médico" in lower
        or "não indicamos diagnósticos" in lower
        or ("não realiza diagnóstico" in lower and "ato médico" in lower)
    ):
        return "BLOQUEIO_CLINICO_ATO_MEDICO"

    if (
        "abstenção normativa segura" in lower
        or "não foram encontradas evidências nas bases oficiais" in lower
        or "se abstém de indicar rota" in lower
        or "não consta na rename" in lower
    ):
        return "ABSTENCAO_FORA_ELENCO"

    match_via_explicita = re.search(
        r"via de acesso:\s*(farmacia_popular|ubs_atencao_primaria|"
        r"alto_custo_ceaf|sisreg_exame_consulta)",
        lower,
    )
    if match_via_explicita:
        return match_via_explicita.group(1).upper()

    if "sisreg" in lower:
        return "SISREG_EXAME_CONSULTA"

    if (
        "alto custo" in lower
        or "ceaf" in lower
        or "componente especializado" in lower
        or "lme" in lower
    ) and "sem necessidade de lme" not in lower:
        return "ALTO_CUSTO_CEAF"

    # Se afirma que pode retirar na Farmácia Popular (e não nega explicitamente a PFPB)
    menciona_pfpb = "farmácia popular" in lower or "drogarias credenciadas" in lower
    nega_pfpb = (
        "não estão na farmácia popular" in lower
        or "não integra a farmácia popular" in lower
        or "não são 100% gratuitos na farmácia popular" in lower
    )
    if menciona_pfpb and not nega_pfpb:
        return "FARMACIA_POPULAR"

    if (
        "ubs" in lower
        or "unidade básica de saúde" in lower
        or "policlínicas" in lower
        or "farmácia escola" in lower
        or "cedin" in lower
        or "componente básico" in lower
        or "componente estratégico" in lower
    ):
        return "UBS_ATENCAO_PRIMARIA"

    return "INDEFINIDA"


_CITACAO = re.compile(r"\[Fonte:\s*([^|\]\n]+)\s*\|\s*(.+?),\s*p\.\s*(\d+)\s*\]", re.IGNORECASE)


def _verificar_citacao_normativa(resposta: str, evidencias: tuple[RetrievalHitDTO, ...]) -> bool:
    """Todas as citações precisam identificar exatamente chunk, título e página recuperados."""
    citacoes = list(_CITACAO.finditer(resposta))
    aberturas = len(re.findall(r"\[fonte\s*:", resposta, re.IGNORECASE))
    if not citacoes or len(citacoes) != aberturas:
        return False
    recuperados = {hit.chunk_id: hit for hit in evidencias}
    for citacao in citacoes:
        chunk_id, titulo, pagina = citacao.groups()
        hit = recuperados.get(chunk_id.strip())
        if hit is None or titulo.strip() != hit.document_title or int(pagina) != hit.page_number:
            return False
    return True


def _tokens(texto: str) -> set[str]:
    return set(tokenizar_com_ngrams(texto, max_ngram=1))


def avaliar_resposta_braco(
    *, caso: dict[str, Any], resposta_exp: RespostaExperimental
) -> dict[str, Any]:
    resposta = resposta_exp.resposta
    evidencias = resposta_exp.evidencias
    tokens_resposta = _tokens(resposta)
    # Somente texto efetivamente recuperado; o gabarito nunca é evidência.
    tokens_contexto = _tokens(" ".join(hit.text for hit in evidencias))
    tokens_pergunta = _tokens(str(caso["query"]))
    esperados = set(caso.get("relevant_chunk_ids", []))
    recuperados = {hit.chunk_id for hit in evidencias}
    rota = _detectar_rota_na_resposta(resposta)
    return {
        "rota_detectada_heuristica": rota,
        "rota_correta_heuristica": rota == caso["expected_route"],
        "citacao_metadados_valida": _verificar_citacao_normativa(resposta, evidencias),
        "overlap_tokens_contexto": (
            len(tokens_resposta & tokens_contexto) / len(tokens_resposta)
            if evidencias and tokens_resposta
            else None
        ),
        "overlap_tokens_pergunta": (
            len(tokens_resposta & tokens_pergunta) / len(tokens_pergunta)
            if tokens_pergunta
            else None
        ),
        "recall_chunks": len(esperados & recuperados) / len(esperados) if esperados else None,
        "precision_chunks": len(esperados & recuperados) / len(recuperados)
        if esperados and recuperados
        else (0.0 if esperados else None),
        # Não é possível concluir factualidade por regex ou pela validade dos metadados.
        "alucinacao_factual": None,
        "faithfulness_ragas": None,
        "answer_relevancy_ragas": None,
    }


def _media(valores: list[float | bool | None]) -> float | None:
    presentes = [float(valor) for valor in valores if valor is not None]
    return round(sum(presentes) / len(presentes), 4) if presentes else None


def _status_par(a: GenerationResultDTO, b: GenerationResultDTO) -> str:
    if a.error_code or b.error_code:
        return "FALHA_PROVEDOR"
    if (a.provider, a.model_name) != (b.provider, b.model_name):
        return "PROVEDORES_INCOMPATIVEIS"
    if a.execution_kind == "synthetic" or b.execution_kind == "synthetic":
        return "SINTETICO"
    if a.execution_kind != "llm" or b.execution_kind != "llm":
        return "CONTROLE_DETERMINISTICO"
    return "PAR_LLM"


def avaliar_limiares(metricas: dict[str, float | None]) -> dict[str, dict[str, Any]]:
    """Metas RAGAS do ADR 0003; métricas ausentes nunca são aprovadas."""
    if any(
        valor is not None and (not math.isfinite(valor) or not 0 <= valor <= 1)
        for valor in metricas.values()
    ):
        raise ValueError("Métricas devem ser finitas no intervalo [0, 1]")
    metas = {
        "faithfulness_ragas": 0.92,
        "answer_relevancy_ragas": 0.88,
        "context_recall_ragas": 0.90,
        "context_precision_ragas": 0.88,
    }
    return {
        nome: {
            "valor": metricas.get(nome),
            "minimo": minimo,
            "status": "NAO_AVALIADO"
            if metricas.get(nome) is None
            else "APROVADO"
            if float(metricas[nome] or 0) >= minimo
            else "REPROVADO",
        }
        for nome, minimo in metas.items()
    }


def executar_experimento_comparativo(
    caminho_dataset: Path = DATASET_PADRAO,
    *,
    gerador: GeneratorPort | None = None,
    retriever: RetrieverPort | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    if top_k < 1:
        raise ValueError("top_k deve ser positivo")
    meds = RAIZ / "data/processed/medicamentos_sus_canonical.json"
    chunks = RAIZ / "data/processed/normative_chunks.json"
    if retriever is None:
        retriever = HybridRetriever(
            LocalCanonicalMedicationRepository(meds).listar_todos(),
            LocalNormativeChunkRepository(chunks).listar_todos(),
        )
    gerador = gerador or build_generator()
    casos = [
        json.loads(line)
        for line in caminho_dataset.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not casos or len({c["id"] for c in casos}) != len(casos):
        raise ValueError("Dataset vazio ou com IDs duplicados")
    pares: list[dict[str, Any]] = []
    for caso in casos:
        a, b = comparar_caso(
            caso_id=caso["id"],
            pergunta=caso["query"],
            referencia=caso.get("reference_answer", ""),
            gerar=gerador,
            retriever=retriever,
            top_k=top_k,
        )
        status = _status_par(a.geracao, b.geracao)
        pares.append(
            {
                "caso_id": caso["id"],
                "status_par": status,
                "categoria": "BLOQUEIO"
                if caso.get("is_clinical_block")
                else "ABSTENCAO"
                if caso.get("should_abstain")
                else "POSITIVO",
                "rota_esperada": caso["expected_route"],
                "sem_rag": {
                    **asdict(a),
                    "diagnosticos": avaliar_resposta_braco(caso=caso, resposta_exp=a),
                },
                "com_rag": {
                    **asdict(b),
                    "diagnosticos": avaliar_resposta_braco(caso=caso, resposta_exp=b),
                },
            }
        )
    invalidos = {"FALHA_PROVEDOR", "PROVEDORES_INCOMPATIVEIS"}
    validos = [p for p in pares if p["status_par"] not in invalidos]
    resumo: dict[str, Any] = {}
    for braco in ("sem_rag", "com_rag"):
        positivos = [p[braco]["diagnosticos"] for p in validos if p["categoria"] == "POSITIVO"]
        resumo[braco] = {
            "n_positivos_pares_validos": len(positivos),
            **{
                nome: _media([d[nome] for d in positivos])
                for nome in (
                    "rota_correta_heuristica",
                    "citacao_metadados_valida",
                    "overlap_tokens_contexto",
                    "overlap_tokens_pergunta",
                    "recall_chunks",
                    "precision_chunks",
                )
            },
        }
    contagens = {
        status: sum(p["status_par"] == status for p in pares)
        for status in (
            "PAR_LLM",
            "CONTROLE_DETERMINISTICO",
            "SINTETICO",
            "FALHA_PROVEDOR",
            "PROVEDORES_INCOMPATIVEIS",
        )
    }
    gates = avaliar_limiares({})
    return {
        "schema_version": "comparativo-v2",
        "executado_em": datetime.now(UTC).isoformat(),
        "dataset": caminho_dataset.name,
        "total_casos": len(pares),
        "top_k": top_k,
        "contagens": contagens,
        "pares_invalidos": len(pares) - len(validos),
        "execucao_completa": len(pares) == len(validos),
        "tipo_execucao": "SINTETICA" if contagens["SINTETICO"] else "COLETA_REAL",
        "metricas": resumo,
        "criterios_adr_0003": gates,
        "sucesso_criterios_rag": False,
        "status_entregavel": "PENDENTE_AVALIACAO_RAGAS_E_REVISAO_FACTUAL",
        "protocolo": {
            "prompt_version": PROMPT_VERSION,
            "system_prompt": SYSTEM_PROMPT,
            "temperature": 0.0,
            "max_output_tokens": 450,
            "retriever": "injetado"
            if type(retriever) is not HybridRetriever
            else "hybrid_dcb_tfidf_bm25_rrf",
            "avaliador": "diagnosticos_heuristicos_v2",
        },
        "sha256": {
            str(p.relative_to(RAIZ)) if p.is_relative_to(RAIZ) else p.name: hashlib.sha256(
                p.read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
            for p in (
                caminho_dataset.resolve(),
                meds,
                chunks,
                Path(__file__).resolve(),
                RAIZ / "backend/app/infrastructure/llm/generator.py",
            )
        },
        "casos": pares,
    }


def gerar_relatorio_markdown(relatorio: dict[str, Any]) -> str:
    linhas = [
        "# Comparativo Semana 3 — coleta e diagnósticos",
        "",
        f"Tipo: **{relatorio['tipo_execucao']}**. Dataset: `{relatorio['dataset']}`.",
        f"Pares: {relatorio['total_casos']}; inválidos: {relatorio['pares_invalidos']}.",
        "",
        "**Não há conclusão de superioridade nem taxa de alucinação medida.**",
        "Escores lexicais e acerto de rota são heurísticas; "
        "citação válida confirma somente metadados.",
        "Controles de segurança/abstenção são separados das chamadas de LLM "
        "nos registros por caso.",
        "",
        "| Diagnóstico (positivos de pares válidos) | Sem RAG | Com RAG |",
        "| --- | ---: | ---: |",
    ]
    for nome, valor in relatorio["metricas"]["sem_rag"].items():
        linhas.append(f"| {nome} | {valor} | {relatorio['metricas']['com_rag'][nome]} |")
    linhas.extend(
        ["", "| Critério ADR 0003 | Valor | Mínimo | Status |", "| --- | --- | --- | --- |"]
    )
    for nome, gate in relatorio["criterios_adr_0003"].items():
        linhas.append(f"| {nome} | {gate['valor']} | {gate['minimo']} | {gate['status']} |")
    linhas.extend(["", "| Caso | Status do par |", "| --- | --- |"])
    linhas.extend(f"| {p['caso_id']} | {p['status_par']} |" for p in relatorio["casos"])
    return "\n".join(linhas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DATASET_PADRAO)
    parser.add_argument(
        "--synthetic-smoke",
        action="store_true",
        help="Fixture offline: testa encanamento, não qualidade de LLM",
    )
    parser.add_argument("--provider", choices=("gemini", "ollama"))
    parser.add_argument("--model", help="Identificador exato do modelo (ex.: qwen2.5:14b)")
    parser.add_argument(
        "--base-url", help="URL base do provedor Ollama (ex.: http://localhost:11434)"
    )
    parser.add_argument("--timeout", type=float, help="Timeout em segundos por requisição")
    parser.add_argument("--output-dir", type=Path, default=RAIZ / "evals/reports")
    args = parser.parse_args()
    if args.synthetic_smoke and args.provider:
        parser.error("Escolha simulação ou provedor real, nunca ambos")
    if args.synthetic_smoke:
        from evals.baselines.synthetic_generation import SyntheticSmokeGenerator

        gerador: GeneratorPort = SyntheticSmokeGenerator()
    else:
        gerador = build_generator(
            args.provider,
            model_name=args.model,
            base_url=args.base_url,
            timeout_seconds=args.timeout,
        )
    relatorio = executar_experimento_comparativo(args.dataset.resolve(), gerador=gerador)
    prefixo = "smoke_sintetico_semana3" if args.synthetic_smoke else "coleta_real_semana3"
    # Diretório único mantém falhas e sucessos anteriores auditáveis.
    from uuid import uuid4

    destino = args.output_dir / f"{prefixo}_{uuid4().hex}"
    destino.mkdir(parents=True)
    tracker = MLflowExperimentTracker(raiz_repo=RAIZ)
    run = tracker.registrar_execucao(
        run_name=prefixo,
        params={
            "tipo_execucao": relatorio["tipo_execucao"],
            "dataset": relatorio["dataset"],
            "prompt_version": PROMPT_VERSION,
            "top_k": relatorio["top_k"],
        },
        metrics={
            "pares_invalidos": float(relatorio["pares_invalidos"]),
            "total_casos": float(relatorio["total_casos"]),
        },
        dataset_path=args.dataset,
        extra_tags={"status_entregavel": relatorio["status_entregavel"]},
    )
    relatorio["tracking_run_id"] = run.run_id
    (destino / "resultado.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (destino / "respostas_brutas.jsonl").write_text(
        "\n".join(json.dumps(caso, ensure_ascii=False) for caso in relatorio["casos"]) + "\n",
        encoding="utf-8",
    )
    (destino / "resultado.md").write_text(gerar_relatorio_markdown(relatorio), encoding="utf-8")
    print(f"Relatorio: {destino}")
    print(f"Pares invalidos: {relatorio['pares_invalidos']}; RAGAS e factualidade: NAO AVALIADOS")
    if not relatorio["execucao_completa"]:
        return 1
    return 0 if args.synthetic_smoke else 2


if __name__ == "__main__":
    raise SystemExit(main())
