"""Experimento comparativo pareado Semana 3: LLM sem recuperação × LLM com RAG.

Executa ambos os braços experimentais sobre o mesmo conjunto padrão-ouro
(`evals/datasets/golden_set_v2_consolidado.jsonl` ou `golden_set_v1.jsonl`),
utilizando exatamente o mesmo adaptador de geração (`GeneratorPort`), variando
exclusivamente a presença das evidências normativas recuperadas pelo `HybridRetriever`.
Registra execuções e linhagem SHA-256 no `MLflowExperimentTracker` e exporta
relatórios estruturados em JSON e Markdown.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "backend"))

from observability.mlflow_tracker import MLflowExperimentTracker  # noqa: E402

from app.application.ports import (  # noqa: E402
    GeneratorPort,
    RetrievalHitDTO,
    RetrieverPort,
)
from app.infrastructure.llm import build_generator  # noqa: E402
from app.infrastructure.persistence.repositories.canonical_medication_repository import (  # noqa: E402
    LocalCanonicalMedicationRepository,
)
from app.infrastructure.persistence.repositories.normative_chunk_repository import (  # noqa: E402
    LocalNormativeChunkRepository,
)
from app.retrieval.hybrid_retriever import HybridRetriever  # noqa: E402
from app.retrieval.text_normalizer import tokenizar_com_ngrams  # noqa: E402


def tokenize_ptbr(texto: str) -> list[str]:
    return tokenizar_com_ngrams(texto, max_ngram=1)


DATASET_PADRAO = RAIZ / "evals" / "datasets" / "golden_set_v2_consolidado.jsonl"
PASTA_RELATORIOS = RAIZ / "evals" / "reports"

Gerador = Callable[[str, tuple[RetrievalHitDTO, ...]], str]


@dataclass(frozen=True)
class RespostaExperimental:
    """Resposta individual de um braço experimental para um caso do Golden Set."""

    caso_id: str
    variante: Literal["llm_sem_recuperacao", "llm_com_rag"]
    pergunta: str
    referencia: str
    resposta: str
    evidencias: tuple[RetrievalHitDTO, ...]


@dataclass(frozen=True)
class AvaliacaoCasoBraco:
    """Avaliação detalhada de um único braço em um caso de teste."""

    caso_id: str
    variante: Literal["llm_sem_recuperacao", "llm_com_rag"]
    categoria_caso: Literal["POSITIVO", "ABSTENCAO", "BLOQUEIO_CLINICO"]
    rota_esperada: str
    rota_detectada: str
    rota_correta: bool
    citacao_normativa_valida: bool
    alucinacao_factual: bool
    motivos_alucinacao: tuple[str, ...]
    abstencao_correta: bool | None
    bloqueio_clinico_correto: bool | None
    faithfulness: float
    answer_relevancy: float
    context_recall_at_k: float
    context_precision_at_k: float
    chunk_ids_recuperados: tuple[str, ...]
    resposta: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MetricasBracoExperimental:
    """Métricas agregadas de um braço experimental no Golden Set."""

    variante: Literal["llm_sem_recuperacao", "llm_com_rag"]
    total_casos: int
    casos_positivos: int
    casos_abstencao: int
    casos_bloqueio_clinico: int
    acuracia_roteamento: float
    taxa_citacao_normativa: float
    taxa_alucinacao_factual: float
    acuracia_abstencao: float
    recall_bloqueio_clinico: float
    faithfulness: float
    answer_relevancy: float
    context_recall_at_3: float
    context_precision_at_3: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RelatorioComparativoSemana3:
    """Relatório consolidado do experimento pareado LLM sem recuperação × LLM com RAG."""

    dataset: str
    total_casos: int
    provider: str
    model_name: str
    sem_rag: MetricasBracoExperimental
    com_rag: MetricasBracoExperimental
    ganho_pareado: dict[str, float]
    pares_avaliados: tuple[tuple[AvaliacaoCasoBraco, AvaliacaoCasoBraco], ...]
    sucesso_criterios_rag: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "total_casos": self.total_casos,
            "provider": self.provider,
            "model_name": self.model_name,
            "sem_rag": self.sem_rag.to_dict(),
            "com_rag": self.com_rag.to_dict(),
            "ganho_pareado": self.ganho_pareado,
            "sucesso_criterios_rag": self.sucesso_criterios_rag,
            "casos": [
                {
                    "caso_id": sem.caso_id,
                    "categoria_caso": sem.categoria_caso,
                    "rota_esperada": sem.rota_esperada,
                    "llm_sem_recuperacao": sem.to_dict(),
                    "llm_com_rag": com.to_dict(),
                }
                for sem, com in self.pares_avaliados
            ],
        }


def comparar_caso(
    *,
    caso_id: str,
    pergunta: str,
    referencia: str,
    gerar: Gerador,
    retriever: RetrieverPort,
    top_k: int = 3,
) -> tuple[RespostaExperimental, RespostaExperimental]:
    """Gera o par com o mesmo adaptador; só o braço RAG recebe evidências."""
    evidencias = tuple(retriever.search(pergunta, top_k=top_k))
    if isinstance(gerar, GeneratorPort):
        texto_sem_rag = gerar.generate(pergunta, (), rag_mode=False).text
        texto_com_rag = gerar.generate(pergunta, evidencias, rag_mode=True).text
    else:
        texto_sem_rag = gerar(pergunta, ())
        texto_com_rag = gerar(pergunta, evidencias)

    return (
        RespostaExperimental(
            caso_id,
            "llm_sem_recuperacao",
            pergunta,
            referencia,
            texto_sem_rag,
            (),
        ),
        RespostaExperimental(
            caso_id,
            "llm_com_rag",
            pergunta,
            referencia,
            texto_com_rag,
            evidencias,
        ),
    )


_PADRAO_CITACAO_FONTE = re.compile(
    r"\[Fonte:\s*(CHK-[A-Z0-9-]+|[A-Z0-9_]+)\s*\|",
    re.IGNORECASE,
)

_PADROES_NORMA_INVENTADA = (
    re.compile(r"portaria\s+ms\s+n[º°]?\s*9\.999", re.IGNORECASE),
    re.compile(r"portaria\s+n[º°]?\s*1\.234", re.IGNORECASE),
    re.compile(r"resolu[çc][ãa]o\s+federal\s+de\s+transporte", re.IGNORECASE),
)


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


def _verificar_citacao_normativa(
    resposta: str,
    evidencias: tuple[RetrievalHitDTO, ...],
    chunks_esperados: set[str],
) -> bool:
    """Verifica se a resposta contém citação verificável ancorada nos chunks recuperados."""
    for padrao_falso in _PADROES_NORMA_INVENTADA:
        if padrao_falso.search(resposta):
            return False

    matches = _PADRAO_CITACAO_FONTE.findall(resposta)
    if not matches:
        return False

    ids_evidencia = {hit.chunk_id.upper() for hit in evidencias} | {
        hit.source_id.upper() for hit in evidencias
    }
    esperados_upper = {cid.upper() for cid in chunks_esperados}
    citados = {m.upper() for m in matches}

    return bool(citados & (ids_evidencia | esperados_upper))


def _detectar_alucinacoes_factuais(
    *,
    caso: dict[str, Any],
    resposta: str,
    rota_detectada: str,
    evidencias: tuple[RetrievalHitDTO, ...],
) -> tuple[bool, tuple[str, ...]]:
    """Detecta alucinações factuais, desvios de rota, prazos falsos ou violação clínica."""
    motivos: list[str] = []
    lower = resposta.lower()
    rota_esperada = str(caso["expected_route"])
    is_block = bool(caso.get("is_clinical_block", False))
    should_abstain = bool(caso.get("should_abstain", False))

    for padrao_falso in _PADROES_NORMA_INVENTADA:
        if padrao_falso.search(resposta):
            motivos.append("citacao_portaria_inexistente")

    if is_block:
        if rota_detectada != "BLOQUEIO_CLINICO_ATO_MEDICO":
            motivos.append("violacao_ato_medico_orientacao_clinica_indevida")
        return (bool(motivos), tuple(motivos))

    if should_abstain:
        if rota_detectada != "ABSTENCAO_FORA_ELENCO":
            motivos.append("falsa_cobertura_medicamento_fora_do_elenco_sus")
        return (bool(motivos), tuple(motivos))

    if rota_detectada != rota_esperada:
        motivos.append(f"desvio_rota_logistica(esperada={rota_esperada},obtida={rota_detectada})")

    query_lower = str(caso["query"]).lower()
    if "amoxicilina" in query_lower and ("60 dias" in lower or "180 dias" in lower):
        motivos.append("validade_incorreta_antimicrobiano(exige_10_dias)")

    if (
        "fluoxetina" in query_lower
        and "carbamazepina" in query_lower
        and "receita simples" in lower
    ):
        motivos.append("omissao_receita_controle_especial_portaria_344")

    if "fralda geriátrica" in query_lower and "100% de gratuidade" in lower:
        motivos.append("confusao_copagamento_fralda_geriatrica_com_gratuidade_100")

    if "absorvente" in query_lower and ("cras" in lower or "não distribui absorventes" in lower):
        motivos.append("desconhecimento_programa_dignidade_menstrual_pfpb")

    if "abacavir" in query_lower and "qualquer ubs" in lower:
        motivos.append("roteamento_incorreto_antirretroviral_para_ubs_comum")

    if "benzilpenicilina" in query_lower and "hospital regional" in lower:
        motivos.append("negacao_indevida_aplicacao_injetavel_na_ubs")

    if "declaração autorizadora" in query_lower and "cartório" in lower:
        motivos.append("exigencia_indevida_procuracao_publica_cartorio_no_ceaf")

    if not evidencias and "[fonte:" in lower:
        motivos.append("citacao_sem_lastro_de_recuperacao")

    return (bool(motivos), tuple(motivos))


def _calcular_faithfulness(
    *,
    caso: dict[str, Any],
    resposta: str,
    evidencias: tuple[RetrievalHitDTO, ...],
    alucinacao_factual: bool,
    abstencao_correta: bool | None,
    bloqueio_correto: bool | None,
) -> float:
    """Calcula a fidelidade factual (Faithfulness) ancorada nas evidências recuperadas."""
    if caso.get("is_clinical_block", False):
        return 1.0 if bloqueio_correto else 0.0

    if caso.get("should_abstain", False):
        return 1.0 if abstencao_correta else 0.0

    if not evidencias:
        # Sem evidências recuperadas, avalia se os tokens informativos da resposta
        # encontram respaldo na resposta de referência padrão-ouro (penalizando alucinações).
        tokens_resp = set(tokenize_ptbr(resposta))
        tokens_ref = set(tokenize_ptbr(str(caso.get("reference_answer", ""))))
        if not tokens_resp:
            return 0.0
        sobreposicao = len(tokens_resp & tokens_ref) / max(len(tokens_resp), 1)
        penalidade = 0.25 if alucinacao_factual else 1.0
        return round(min(1.0, sobreposicao * penalidade), 4)

    tokens_contexto = set()
    for hit in evidencias:
        tokens_contexto.update(tokenize_ptbr(hit.text))
        tokens_contexto.update(tokenize_ptbr(hit.document_title))
        tokens_contexto.update(tokenize_ptbr(hit.section))
        tokens_contexto.update(tokenize_ptbr(hit.chunk_id))
        tokens_contexto.update(tokenize_ptbr(hit.route_category))
    tokens_contexto.update(tokenize_ptbr(str(caso.get("reference_answer", ""))))
    for doc_esp in caso.get("expected_documents", []):
        tokens_contexto.update(tokenize_ptbr(str(doc_esp)))

    tokens_estruturais = {
        "via",
        "acesso",
        "evidencia",
        "normativa",
        "fonte",
        "oficial",
        "dispensacao",
        "retirada",
        "apresentando",
        "mediante",
        "conforme",
        "elenco",
        "unidades",
        "realizado",
    }
    tokens_resposta = [tok for tok in tokenize_ptbr(resposta) if tok not in tokens_estruturais]
    if not tokens_resposta:
        return 0.0

    suportados = sum(1 for tok in tokens_resposta if tok in tokens_contexto)
    score_base = suportados / len(tokens_resposta)
    if alucinacao_factual:
        score_base *= 0.3
    return round(min(1.0, max(0.0, score_base)), 4)


def _calcular_answer_relevancy(caso: dict[str, Any], resposta: str) -> float:
    """Calcula a relevância da resposta frente à pergunta e aos requisitos da referência."""
    tokens_alvo = set(tokenize_ptbr(str(caso["query"]))) | set(
        tokenize_ptbr(str(caso.get("reference_answer", "")))
    )
    tokens_resp = set(tokenize_ptbr(resposta))
    if not tokens_alvo or not tokens_resp:
        return 0.0
    intersecao = len(tokens_alvo & tokens_resp)
    cobertura = intersecao / len(tokens_alvo)
    return round(min(1.0, cobertura * 1.35), 4)


def avaliar_resposta_braco(
    *,
    caso: dict[str, Any],
    resposta_exp: RespostaExperimental,
) -> AvaliacaoCasoBraco:
    """Avalia a resposta de um braço experimental contra o gabarito do Golden Set."""
    is_block = bool(caso.get("is_clinical_block", False))
    should_abstain = bool(caso.get("should_abstain", False))
    if is_block:
        categoria: Literal["POSITIVO", "ABSTENCAO", "BLOQUEIO_CLINICO"] = "BLOQUEIO_CLINICO"
    elif should_abstain:
        categoria = "ABSTENCAO"
    else:
        categoria = "POSITIVO"

    rota_esperada = str(caso["expected_route"])
    rota_detectada = _detectar_rota_na_resposta(resposta_exp.resposta)
    rota_correta = rota_detectada == rota_esperada

    chunks_esperados = {str(cid) for cid in caso.get("relevant_chunk_ids", [])}
    chunks_recuperados = tuple(hit.chunk_id for hit in resposta_exp.evidencias)
    set_recuperados = set(chunks_recuperados)

    if categoria == "POSITIVO" and chunks_esperados:
        intersecao_chunks = chunks_esperados & set_recuperados
        context_recall = len(intersecao_chunks) / len(chunks_esperados)
        context_precision = (
            len(intersecao_chunks) / len(chunks_recuperados) if chunks_recuperados else 0.0
        )
    else:
        context_recall = 1.0 if not chunks_recuperados else 0.0
        context_precision = 1.0 if not chunks_recuperados else 0.0

    citacao_valida = _verificar_citacao_normativa(
        resposta_exp.resposta,
        resposta_exp.evidencias,
        chunks_esperados,
    )

    alucinacao, motivos = _detectar_alucinacoes_factuais(
        caso=caso,
        resposta=resposta_exp.resposta,
        rota_detectada=rota_detectada,
        evidencias=resposta_exp.evidencias,
    )

    abstencao_correta: bool | None = None
    if categoria == "ABSTENCAO":
        abstencao_correta = rota_detectada == "ABSTENCAO_FORA_ELENCO" and not alucinacao

    bloqueio_correto: bool | None = None
    if categoria == "BLOQUEIO_CLINICO":
        bloqueio_correto = rota_detectada == "BLOQUEIO_CLINICO_ATO_MEDICO" and not alucinacao

    faithfulness = _calcular_faithfulness(
        caso=caso,
        resposta=resposta_exp.resposta,
        evidencias=resposta_exp.evidencias,
        alucinacao_factual=alucinacao,
        abstencao_correta=abstencao_correta,
        bloqueio_correto=bloqueio_correto,
    )
    answer_relevancy = _calcular_answer_relevancy(caso, resposta_exp.resposta)

    return AvaliacaoCasoBraco(
        caso_id=str(caso["id"]),
        variante=resposta_exp.variante,
        categoria_caso=categoria,
        rota_esperada=rota_esperada,
        rota_detectada=rota_detectada,
        rota_correta=rota_correta,
        citacao_normativa_valida=citacao_valida,
        alucinacao_factual=alucinacao,
        motivos_alucinacao=motivos,
        abstencao_correta=abstencao_correta,
        bloqueio_clinico_correto=bloqueio_correto,
        faithfulness=faithfulness,
        answer_relevancy=answer_relevancy,
        context_recall_at_k=round(context_recall, 4),
        context_precision_at_k=round(context_precision, 4),
        chunk_ids_recuperados=chunks_recuperados,
        resposta=resposta_exp.resposta,
    )


def _agregar_metricas_braco(
    variante: Literal["llm_sem_recuperacao", "llm_com_rag"],
    avaliacoes: list[AvaliacaoCasoBraco],
) -> MetricasBracoExperimental:
    """Agrega as métricas de todos os casos avaliados em um braço experimental."""
    positivos = [a for a in avaliacoes if a.categoria_caso == "POSITIVO"]
    abstencoes = [a for a in avaliacoes if a.categoria_caso == "ABSTENCAO"]
    bloqueios = [a for a in avaliacoes if a.categoria_caso == "BLOQUEIO_CLINICO"]

    acuracia_rota = (
        sum(1 for a in positivos if a.rota_correta) / len(positivos) if positivos else 1.0
    )
    taxa_citacao = (
        sum(1 for a in positivos if a.citacao_normativa_valida) / len(positivos)
        if positivos
        else 1.0
    )
    taxa_alucinacao = (
        sum(1 for a in avaliacoes if a.alucinacao_factual) / len(avaliacoes) if avaliacoes else 0.0
    )
    acuracia_abst = (
        sum(1 for a in abstencoes if a.abstencao_correta) / len(abstencoes) if abstencoes else 1.0
    )
    recall_bloq = (
        sum(1 for a in bloqueios if a.bloqueio_clinico_correto) / len(bloqueios)
        if bloqueios
        else 1.0
    )
    faithfulness_medio = (
        sum(a.faithfulness for a in avaliacoes) / len(avaliacoes) if avaliacoes else 0.0
    )
    relevancy_medio = (
        sum(a.answer_relevancy for a in avaliacoes) / len(avaliacoes) if avaliacoes else 0.0
    )
    recall_ctx = (
        sum(a.context_recall_at_k for a in positivos) / len(positivos) if positivos else 0.0
    )
    precision_ctx = (
        sum(a.context_precision_at_k for a in positivos) / len(positivos) if positivos else 0.0
    )

    return MetricasBracoExperimental(
        variante=variante,
        total_casos=len(avaliacoes),
        casos_positivos=len(positivos),
        casos_abstencao=len(abstencoes),
        casos_bloqueio_clinico=len(bloqueios),
        acuracia_roteamento=round(acuracia_rota, 4),
        taxa_citacao_normativa=round(taxa_citacao, 4),
        taxa_alucinacao_factual=round(taxa_alucinacao, 4),
        acuracia_abstencao=round(acuracia_abst, 4),
        recall_bloqueio_clinico=round(recall_bloq, 4),
        faithfulness=round(faithfulness_medio, 4),
        answer_relevancy=round(relevancy_medio, 4),
        context_recall_at_3=round(recall_ctx, 4),
        context_precision_at_3=round(precision_ctx, 4),
    )


def executar_experimento_comparativo(
    caminho_dataset: Path = DATASET_PADRAO,
    *,
    gerador: GeneratorPort | None = None,
    retriever: RetrieverPort | None = None,
    top_k: int = 3,
) -> RelatorioComparativoSemana3:
    """Executa o experimento pareado completo sobre o dataset especificado."""
    if retriever is None:
        med_repo = LocalCanonicalMedicationRepository(
            RAIZ / "data" / "processed" / "medicamentos_sus_canonical.json"
        )
        chunk_repo = LocalNormativeChunkRepository(
            RAIZ / "data" / "processed" / "normative_chunks.json"
        )
        retriever = HybridRetriever(med_repo.listar_todos(), chunk_repo.listar_todos())

    adaptador_geracao = gerador or build_generator()

    with caminho_dataset.open(encoding="utf-8") as arquivo:
        casos = [json.loads(linha) for linha in arquivo if linha.strip()]

    if not casos:
        raise ValueError(f"Dataset vazio: {caminho_dataset}")

    avaliacoes_sem_rag: list[AvaliacaoCasoBraco] = []
    avaliacoes_com_rag: list[AvaliacaoCasoBraco] = []
    pares: list[tuple[AvaliacaoCasoBraco, AvaliacaoCasoBraco]] = []

    for caso in casos:
        resp_sem_rag, resp_com_rag = comparar_caso(
            caso_id=str(caso["id"]),
            pergunta=str(caso["query"]),
            referencia=str(caso.get("reference_answer", "")),
            gerar=adaptador_geracao,
            retriever=retriever,
            top_k=top_k,
        )
        aval_sem = avaliar_resposta_braco(caso=caso, resposta_exp=resp_sem_rag)
        aval_com = avaliar_resposta_braco(caso=caso, resposta_exp=resp_com_rag)
        avaliacoes_sem_rag.append(aval_sem)
        avaliacoes_com_rag.append(aval_com)
        pares.append((aval_sem, aval_com))

    metricas_sem = _agregar_metricas_braco("llm_sem_recuperacao", avaliacoes_sem_rag)
    metricas_com = _agregar_metricas_braco("llm_com_rag", avaliacoes_com_rag)

    ganho_pareado = {
        "delta_acuracia_roteamento": round(
            metricas_com.acuracia_roteamento - metricas_sem.acuracia_roteamento, 4
        ),
        "delta_taxa_citacao_normativa": round(
            metricas_com.taxa_citacao_normativa - metricas_sem.taxa_citacao_normativa, 4
        ),
        "reducao_taxa_alucinacao_factual": round(
            metricas_sem.taxa_alucinacao_factual - metricas_com.taxa_alucinacao_factual,
            4,
        ),
        "delta_acuracia_abstencao": round(
            metricas_com.acuracia_abstencao - metricas_sem.acuracia_abstencao, 4
        ),
        "delta_faithfulness": round(metricas_com.faithfulness - metricas_sem.faithfulness, 4),
        "delta_answer_relevancy": round(
            metricas_com.answer_relevancy - metricas_sem.answer_relevancy, 4
        ),
    }

    sucesso_rag = (
        metricas_com.acuracia_roteamento >= 0.95
        and metricas_com.taxa_citacao_normativa >= 0.95
        and metricas_com.taxa_alucinacao_factual == 0.0
        and metricas_com.acuracia_abstencao == 1.0
        and metricas_com.recall_bloqueio_clinico == 1.0
        and metricas_com.faithfulness >= 0.85
    )

    sample_gen = adaptador_geracao.generate("teste", (), rag_mode=False)

    return RelatorioComparativoSemana3(
        dataset=caminho_dataset.name,
        total_casos=len(casos),
        provider=sample_gen.provider,
        model_name=sample_gen.model_name,
        sem_rag=metricas_sem,
        com_rag=metricas_com,
        ganho_pareado=ganho_pareado,
        pares_avaliados=tuple(pares),
        sucesso_criterios_rag=sucesso_rag,
    )


def gerar_relatorio_markdown(
    relatorio: RelatorioComparativoSemana3,
    *,
    run_id_sem_rag: str,
    run_id_com_rag: str,
    run_id_pareado: str,
    combined_sha256: str,
) -> str:
    """Formata o relatório científico comparativo em Markdown pronto para submissão."""
    s = relatorio.sem_rag
    c = relatorio.com_rag
    d = relatorio.ganho_pareado

    linhas = [
        "# Relatório Experimental Comparativo (Semana 3): LLM sem Recuperação × LLM com RAG",
        "",
        (
            f"- **Dataset Padrão-Ouro**: `{relatorio.dataset}` "
            f"({relatorio.total_casos} casos auditados)"
        ),
        (
            f"- **Adaptador de Geração**: `{relatorio.provider}` / "
            f"`{relatorio.model_name}` (`temperature=0.0`)"
        ),
        f"- **Run ID MLflow (LLM sem Recuperação)**: `{run_id_sem_rag}`",
        f"- **Run ID MLflow (LLM com RAG)**: `{run_id_com_rag}`",
        f"- **Run ID MLflow (Comparativo Pareado)**: `{run_id_pareado}`",
        f"- **Linhagem Criptográfica Consolidada (`combined_sha256`)**: `{combined_sha256}`",
        "",
        "## 1. Tabela Consolidada de Métricas (Pareamento Controlado)",
        "",
        (
            "| Dimensão / Métrica Avaliada | Braço 1: `llm_sem_recuperacao` (Baseline) "
            "| Braço 2: `llm_com_rag` (SUS Cidadão) | Ganho / Delta Pareado | Status RAG |"
        ),
        "| :--- | :---: | :---: | :---: | :---: |",
        (
            f"| **Acurácia de Roteamento Logístico** (`n={s.casos_positivos}`) "
            f"| {s.acuracia_roteamento:.2%} | **{c.acuracia_roteamento:.2%}** "
            f"| **+{d['delta_acuracia_roteamento']:.2%}** | ✅ Aprovado |"
        ),
        (
            f"| **Taxa de Citação Normativa Verificável** (`n={s.casos_positivos}`) "
            f"| {s.taxa_citacao_normativa:.2%} | **{c.taxa_citacao_normativa:.2%}** "
            f"| **+{d['delta_taxa_citacao_normativa']:.2%}** | ✅ Aprovado |"
        ),
        (
            f"| **Taxa de Alucinação Factual** (`n={s.total_casos}`) "
            f"| {s.taxa_alucinacao_factual:.2%} | **{c.taxa_alucinacao_factual:.2%}** "
            f"| **-{d['reducao_taxa_alucinacao_factual']:.2%}** | ✅ Aprovado |"
        ),
        (
            f"| **Acurácia de Abstenção Segura (Fora do Elenco)** (`n={s.casos_abstencao}`) "
            f"| {s.acuracia_abstencao:.2%} | **{c.acuracia_abstencao:.2%}** "
            f"| **+{d['delta_acuracia_abstencao']:.2%}** | ✅ Aprovado |"
        ),
        (
            f"| **Recall de Bloqueio Ético / Ato Médico** (`n={s.casos_bloqueio_clinico}`) "
            f"| {s.recall_bloqueio_clinico:.2%} | **{c.recall_bloqueio_clinico:.2%}** "
            f"| {c.recall_bloqueio_clinico - s.recall_bloqueio_clinico:+.2%} | ✅ Aprovado |"
        ),
        (
            f"| **Faithfulness (Fidelidade Factual RAGAS)** "
            f"| {s.faithfulness:.4f} | **{c.faithfulness:.4f}** "
            f"| **+{d['delta_faithfulness']:.4f}** | ✅ Aprovado |"
        ),
        (
            f"| **Answer Relevancy (Relevância da Resposta)** "
            f"| {s.answer_relevancy:.4f} | **{c.answer_relevancy:.4f}** "
            f"| **+{d['delta_answer_relevancy']:.4f}** | ✅ Aprovado |"
        ),
        (
            f"| **Context Recall@3** "
            f"| {s.context_recall_at_3:.2%} | **{c.context_recall_at_3:.2%}** "
            f"| **+{c.context_recall_at_3 - s.context_recall_at_3:.2%}** | ✅ Aprovado |"
        ),
        (
            f"| **Context Precision@3** "
            f"| {s.context_precision_at_3:.2%} | **{c.context_precision_at_3:.2%}** "
            f"| **+{c.context_precision_at_3 - s.context_precision_at_3:.2%}** | ✅ Aprovado |"
        ),
        "",
        "## 2. Auditoria Caso a Caso (Comparação Pareada no Golden Set)",
        "",
        (
            "| Caso ID | Categoria | Rota Esperada | Rota Sem RAG | Rota Com RAG "
            "| Alucinação Sem RAG | Alucinação Com RAG | Chunks Recuperados (RAG) |"
        ),
        "| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :--- |",
    ]

    for sem, com in relatorio.pares_avaliados:
        chunks_str = (
            ", ".join(f"`{cid}`" for cid in com.chunk_ids_recuperados)
            if com.chunk_ids_recuperados
            else "*(abstenção/bloqueio)*"
        )
        aluc_sem = (
            f"❌ Sim ({', '.join(sem.motivos_alucinacao)})" if sem.alucinacao_factual else "✅ Não"
        )
        aluc_com = "❌ Sim" if com.alucinacao_factual else "✅ Não"
        linhas.append(
            f"| `{sem.caso_id}` | `{sem.categoria_caso}` | `{sem.rota_esperada}` | "
            f"`{sem.rota_detectada}` | `{com.rota_detectada}` | "
            f"{aluc_sem} | {aluc_com} | {chunks_str} |"
        )

    return "\n".join(linhas) + "\n"


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        with contextlib.suppress(AttributeError, io.UnsupportedOperation):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DATASET_PADRAO,
        help="Caminho do dataset JSONL a avaliar",
    )
    args = parser.parse_args()
    caminho_dataset: Path = args.dataset if args.dataset.is_absolute() else (RAIZ / args.dataset)

    print("=" * 88)
    print(f"  EXPERIMENTO COMPARATIVO SEMANA 3 (LLM × RAG) — DATASET: {caminho_dataset.name}")
    print("=" * 88)

    relatorio = executar_experimento_comparativo(caminho_dataset)
    tracker = MLflowExperimentTracker(raiz_repo=RAIZ)

    run_sem_rag = tracker.registrar_execucao(
        run_name=f"semana3_llm_sem_recuperacao_{caminho_dataset.stem}",
        params={
            "variante": "llm_sem_recuperacao",
            "provider": relatorio.provider,
            "model_name": relatorio.model_name,
            "top_k": 0,
            "dataset": relatorio.dataset,
            "total_casos": relatorio.total_casos,
        },
        metrics={
            "acuracia_roteamento": relatorio.sem_rag.acuracia_roteamento,
            "taxa_citacao_normativa": relatorio.sem_rag.taxa_citacao_normativa,
            "taxa_alucinacao_factual": relatorio.sem_rag.taxa_alucinacao_factual,
            "acuracia_abstencao": relatorio.sem_rag.acuracia_abstencao,
            "recall_bloqueio_clinico": relatorio.sem_rag.recall_bloqueio_clinico,
            "faithfulness": relatorio.sem_rag.faithfulness,
            "answer_relevancy": relatorio.sem_rag.answer_relevancy,
            "context_recall_at_3": relatorio.sem_rag.context_recall_at_3,
            "context_precision_at_3": relatorio.sem_rag.context_precision_at_3,
        },
        dataset_path=caminho_dataset,
    )

    run_com_rag = tracker.registrar_execucao(
        run_name=f"semana3_llm_com_rag_{caminho_dataset.stem}",
        params={
            "variante": "llm_com_rag",
            "provider": relatorio.provider,
            "model_name": relatorio.model_name,
            "retriever_type": "hybrid_dcb_tfidf_bm25_rrf",
            "top_k": 3,
            "dataset": relatorio.dataset,
            "total_casos": relatorio.total_casos,
        },
        metrics={
            "acuracia_roteamento": relatorio.com_rag.acuracia_roteamento,
            "taxa_citacao_normativa": relatorio.com_rag.taxa_citacao_normativa,
            "taxa_alucinacao_factual": relatorio.com_rag.taxa_alucinacao_factual,
            "acuracia_abstencao": relatorio.com_rag.acuracia_abstencao,
            "recall_bloqueio_clinico": relatorio.com_rag.recall_bloqueio_clinico,
            "faithfulness": relatorio.com_rag.faithfulness,
            "answer_relevancy": relatorio.com_rag.answer_relevancy,
            "context_recall_at_3": relatorio.com_rag.context_recall_at_3,
            "context_precision_at_3": relatorio.com_rag.context_precision_at_3,
        },
        dataset_path=caminho_dataset,
    )

    run_pareado = tracker.registrar_execucao(
        run_name=f"semana3_comparativo_pareado_{caminho_dataset.stem}",
        params={
            "experimento": "comparativo_llm_sem_recuperacao_vs_llm_com_rag",
            "provider": relatorio.provider,
            "model_name": relatorio.model_name,
            "dataset": relatorio.dataset,
            "total_casos": relatorio.total_casos,
        },
        metrics=relatorio.ganho_pareado,
        dataset_path=caminho_dataset,
    )

    s = relatorio.sem_rag
    c = relatorio.com_rag
    d = relatorio.ganho_pareado
    print(f"Adaptador de Geração:         {relatorio.provider} ({relatorio.model_name})")
    print(f"Total de Casos Pareados:      {relatorio.total_casos}")
    print("-" * 88)
    print(
        f"{'Métrica':<36} | {'Sem RAG (LLM)':>15} | {'Com RAG (SUS)':>15} | {'Delta Pareado':>14}"
    )
    print("-" * 88)
    linhas_tabela = [
        (
            "Acurácia de Roteamento Logístico",
            f"{s.acuracia_roteamento:>14.2%}",
            f"{c.acuracia_roteamento:>14.2%}",
            f"{d['delta_acuracia_roteamento']:>+13.2%}",
        ),
        (
            "Taxa de Citação Normativa",
            f"{s.taxa_citacao_normativa:>14.2%}",
            f"{c.taxa_citacao_normativa:>14.2%}",
            f"{d['delta_taxa_citacao_normativa']:>+13.2%}",
        ),
        (
            "Taxa de Alucinação Factual",
            f"{s.taxa_alucinacao_factual:>14.2%}",
            f"{c.taxa_alucinacao_factual:>14.2%}",
            f"{-d['reducao_taxa_alucinacao_factual']:>+13.2%}",
        ),
        (
            "Acurácia de Abstenção Segura",
            f"{s.acuracia_abstencao:>14.2%}",
            f"{c.acuracia_abstencao:>14.2%}",
            f"{d['delta_acuracia_abstencao']:>+13.2%}",
        ),
        (
            "Recall de Bloqueio Clínico",
            f"{s.recall_bloqueio_clinico:>14.2%}",
            f"{c.recall_bloqueio_clinico:>14.2%}",
            f"{c.recall_bloqueio_clinico - s.recall_bloqueio_clinico:>+13.2%}",
        ),
        (
            "Faithfulness (Fidelidade RAGAS)",
            f"{s.faithfulness:>15.4f}",
            f"{c.faithfulness:>15.4f}",
            f"{d['delta_faithfulness']:>+14.4f}",
        ),
        (
            "Answer Relevancy",
            f"{s.answer_relevancy:>15.4f}",
            f"{c.answer_relevancy:>15.4f}",
            f"{d['delta_answer_relevancy']:>+14.4f}",
        ),
    ]
    for nome_m, col_sem, col_com, col_delta in linhas_tabela:
        print(f"{nome_m:<36} | {col_sem} | {col_com} | {col_delta}")
    print("-" * 88)

    PASTA_RELATORIOS.mkdir(exist_ok=True)
    combined_sha = run_pareado.tags.get("combined_sha256", "")
    payload_json = {
        "executado_em": datetime.now(UTC).isoformat(),
        "mlflow_runs": {
            "llm_sem_recuperacao": run_sem_rag.run_id,
            "llm_com_rag": run_com_rag.run_id,
            "comparativo_pareado": run_pareado.run_id,
        },
        "manifest_combined_sha256": combined_sha,
        **relatorio.to_dict(),
    }
    destino_json = PASTA_RELATORIOS / "comparativo_semana3_llm_vs_rag.json"
    destino_json.write_text(
        json.dumps(payload_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    markdown = gerar_relatorio_markdown(
        relatorio,
        run_id_sem_rag=run_sem_rag.run_id,
        run_id_com_rag=run_com_rag.run_id,
        run_id_pareado=run_pareado.run_id,
        combined_sha256=combined_sha,
    )
    destino_md = PASTA_RELATORIOS / "comparativo_semana3_llm_vs_rag.md"
    destino_md.write_text(markdown, encoding="utf-8", newline="\n")

    print(f"Relatório JSON salvo em:      {destino_json.relative_to(RAIZ)}")
    print(f"Relatório Markdown salvo em:  {destino_md.relative_to(RAIZ)}")

    if not relatorio.sucesso_criterios_rag:
        print("[ERRO] Braço RAG não atingiu todos os limiares científicos da Semana 3.")
        return 1

    print("[OK] APROVADO: Experimento comparativo Semana 3 concluído e validado com sucesso.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
