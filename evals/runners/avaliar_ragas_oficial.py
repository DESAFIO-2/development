"""Estágio 2 do comparativo Semana 3: Avaliação oficial RAGAS (0.4.3) e auditoria factual."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

RAIZ = Path(__file__).resolve().parents[2]
for _cam in (RAIZ, RAIZ / "backend"):
    if str(_cam) not in sys.path:
        sys.path.insert(0, str(_cam))

from observability.mlflow_tracker import MLflowExperimentTracker  # noqa: E402


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


@dataclass(frozen=True)
class EscoresCasoRagas:
    sem_rag_answer_relevancy: float
    com_rag_faithfulness: float
    com_rag_answer_relevancy: float
    com_rag_context_recall: float
    com_rag_context_precision: float


class RagasEvaluatorPort(Protocol):
    evaluator_provider: str
    evaluator_model: str
    embedding_model: str

    def avaliar_par_positivo(
        self,
        *,
        pergunta: str,
        referencia: str,
        resposta_sem_rag: str,
        resposta_com_rag: str,
        contextos_com_rag: list[str],
    ) -> EscoresCasoRagas: ...


def _validar_escore_finito(nome: str, valor: Any) -> float:
    numero = float(valor)
    if not math.isfinite(numero) or numero < 0.0 or numero > 1.0:
        raise ValueError(f"Escore RAGAS inválido ou não finito em {nome}: {valor!r}")
    return round(numero, 4)


def _media_completa(valores: list[float | None], esperado: int) -> float | None:
    if esperado == 0 or len(valores) != esperado or any(v is None for v in valores):
        return None
    finitos = [float(v) for v in valores if v is not None]
    return round(sum(finitos) / len(finitos), 4)


class OfficialRagasCollectionsEvaluator:
    """Adaptador para ragas==0.4.3 (ragas.metrics.collections) via endpoint OpenAI-compatível."""

    def __init__(
        self,
        *,
        evaluator_model: str,
        embedding_model: str,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
        provider_label: str = "ollama_openai_compat",
    ) -> None:
        os.environ["RAGAS_DO_NOT_TRACK"] = "true"
        self.evaluator_provider = provider_label
        self.evaluator_model = evaluator_model
        self.embedding_model = embedding_model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

        openai_mod = importlib.import_module("openai")
        ragas_llms = importlib.import_module("ragas.llms")
        ragas_embeddings = importlib.import_module("ragas.embeddings.base")
        ragas_collections = importlib.import_module("ragas.metrics.collections")

        async_client = openai_mod.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        llm = ragas_llms.llm_factory(
            self.evaluator_model,
            provider="openai",
            client=async_client,
            temperature=0.01,
            max_tokens=2048,
        )
        embeddings = ragas_embeddings.embedding_factory(
            "openai",
            model=self.embedding_model,
            client=async_client,
        )
        self._faithfulness = ragas_collections.Faithfulness(llm=llm)
        self._answer_relevancy = ragas_collections.AnswerRelevancy(
            llm=llm,
            embeddings=embeddings,
            strictness=3,
        )
        self._context_recall = ragas_collections.ContextRecall(llm=llm)
        self._context_precision = ragas_collections.ContextPrecision(llm=llm)

    async def _avaliar_async(
        self,
        *,
        pergunta: str,
        referencia: str,
        resposta_sem_rag: str,
        resposta_com_rag: str,
        contextos_com_rag: list[str],
    ) -> EscoresCasoRagas:
        ar_sem = await self._answer_relevancy.ascore(
            user_input=pergunta,
            response=resposta_sem_rag,
        )
        faith_com = await self._faithfulness.ascore(
            user_input=pergunta,
            response=resposta_com_rag,
            retrieved_contexts=contextos_com_rag,
        )
        ar_com = await self._answer_relevancy.ascore(
            user_input=pergunta,
            response=resposta_com_rag,
        )
        cr_com = await self._context_recall.ascore(
            user_input=pergunta,
            retrieved_contexts=contextos_com_rag,
            reference=referencia,
        )
        cp_com = await self._context_precision.ascore(
            user_input=pergunta,
            reference=referencia,
            retrieved_contexts=contextos_com_rag,
        )
        return EscoresCasoRagas(
            sem_rag_answer_relevancy=_validar_escore_finito(
                "sem_rag.answer_relevancy", ar_sem.value
            ),
            com_rag_faithfulness=_validar_escore_finito("com_rag.faithfulness", faith_com.value),
            com_rag_answer_relevancy=_validar_escore_finito(
                "com_rag.answer_relevancy", ar_com.value
            ),
            com_rag_context_recall=_validar_escore_finito("com_rag.context_recall", cr_com.value),
            com_rag_context_precision=_validar_escore_finito(
                "com_rag.context_precision", cp_com.value
            ),
        )

    def avaliar_par_positivo(
        self,
        *,
        pergunta: str,
        referencia: str,
        resposta_sem_rag: str,
        resposta_com_rag: str,
        contextos_com_rag: list[str],
    ) -> EscoresCasoRagas:
        return asyncio.run(
            self._avaliar_async(
                pergunta=pergunta,
                referencia=referencia,
                resposta_sem_rag=resposta_sem_rag,
                resposta_com_rag=resposta_com_rag,
                contextos_com_rag=contextos_com_rag,
            )
        )


def gerar_template_auditoria_factual(coleta: dict[str, Any]) -> dict[str, Any]:
    """Gera estrutura auditável para verificação factual independente contra a referência."""
    itens: list[dict[str, Any]] = []
    for caso in coleta.get("casos", []):
        if caso.get("categoria") != "POSITIVO" or caso.get("status_par") != "PAR_LLM":
            continue
        itens.append(
            {
                "caso_id": caso["caso_id"],
                "pergunta": caso["com_rag"]["pergunta"],
                "referencia_normativa": caso["com_rag"]["referencia"],
                "sem_rag": {
                    "resposta": caso["sem_rag"]["geracao"]["text"],
                    "afirmacoes_corretas": 0,
                    "afirmacoes_contraditas": 0,
                    "afirmacoes_nao_verificaveis": 0,
                    "revisado": False,
                    "observacoes": "",
                },
                "com_rag": {
                    "resposta": caso["com_rag"]["geracao"]["text"],
                    "afirmacoes_corretas": 0,
                    "afirmacoes_contraditas": 0,
                    "afirmacoes_nao_verificaveis": 0,
                    "revisado": False,
                    "observacoes": "",
                },
            }
        )
    return {
        "schema_version": "auditoria-factual-v1",
        "instrucoes": (
            "Para cada resposta positiva (sem_rag e com_rag), classifique cada afirmação "
            "factual contra a referencia_normativa em: afirmacoes_corretas, "
            "afirmacoes_contraditas ou afirmacoes_nao_verificaveis, e marque revisado=true."
        ),
        "casos": itens,
    }


def consolidar_auditoria_factual(
    auditoria: dict[str, Any],
    ids_positivos_esperados: set[str],
) -> dict[str, Any]:
    """Calcula taxas factuais com denominadores explícitos somente quando 100% revisado."""
    casos_map = {item["caso_id"]: item for item in auditoria.get("casos", [])}
    if not ids_positivos_esperados or set(casos_map.keys()) != ids_positivos_esperados:
        return {"completa": False, "sem_rag": None, "com_rag": None}

    resumo: dict[str, Any] = {"completa": True}
    for braco in ("sem_rag", "com_rag"):
        corretas = 0
        contraditas = 0
        nao_verificaveis = 0
        casos_com_contradicao = 0
        for cid in sorted(ids_positivos_esperados):
            bloco = casos_map[cid].get(braco, {})
            if bloco.get("revisado") is not True:
                return {"completa": False, "sem_rag": None, "com_rag": None}
            c_ok = int(bloco.get("afirmacoes_corretas", 0))
            c_err = int(bloco.get("afirmacoes_contraditas", 0))
            c_nv = int(bloco.get("afirmacoes_nao_verificaveis", 0))
            if c_ok < 0 or c_err < 0 or c_nv < 0 or (c_ok + c_err + c_nv) == 0:
                return {"completa": False, "sem_rag": None, "com_rag": None}
            corretas += c_ok
            contraditas += c_err
            nao_verificaveis += c_nv
            if c_err > 0:
                casos_com_contradicao += 1
        total_afirmacoes = corretas + contraditas + nao_verificaveis
        resumo[braco] = {
            "total_casos_avaliados": len(ids_positivos_esperados),
            "total_afirmacoes": total_afirmacoes,
            "afirmacoes_corretas": corretas,
            "afirmacoes_contraditas": contraditas,
            "afirmacoes_nao_verificaveis": nao_verificaveis,
            "taxa_contradicao_por_afirmacao": round(contraditas / total_afirmacoes, 4),
            "taxa_nao_verificavel_por_afirmacao": round(nao_verificaveis / total_afirmacoes, 4),
            "taxa_erro_factual_por_afirmacao": round(
                (contraditas + nao_verificaveis) / total_afirmacoes, 4
            ),
            "taxa_casos_com_contradicao": round(
                casos_com_contradicao / len(ids_positivos_esperados), 4
            ),
        }
    return resumo


def avaliar_coleta_ragas(
    coleta: dict[str, Any],
    *,
    avaliador: RagasEvaluatorPort,
    auditoria_factual: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Executa avaliação RAGAS oficial sobre coleta real completa sem regenerar respostas."""
    if coleta.get("tipo_execucao") != "COLETA_REAL":
        raise ValueError(
            "Certificação RAGAS exige tipo_execucao == 'COLETA_REAL'; "
            "execuções sintéticas não podem ser avaliadas como entregável científico."
        )
    if not coleta.get("execucao_completa", False) or int(coleta.get("pares_invalidos", 1)) > 0:
        raise ValueError(
            "Coleta possui pares inválidos ou está incompleta; corrija a coleta antes do RAGAS."
        )

    casos_avaliados: list[dict[str, Any]] = []
    sem_ar_vals: list[float | None] = []
    com_faith_vals: list[float | None] = []
    com_ar_vals: list[float | None] = []
    com_cr_vals: list[float | None] = []
    com_cp_vals: list[float | None] = []
    erros_avaliador = 0
    ids_positivos: set[str] = set()

    for caso in coleta.get("casos", []):
        copia = json.loads(json.dumps(caso))
        eh_positivo_llm = (
            copia.get("categoria") == "POSITIVO" and copia.get("status_par") == "PAR_LLM"
        )
        if not eh_positivo_llm:
            copia["ragas"] = {
                "aplicavel": False,
                "motivo": "CONTROLE_DETERMINISTICO_OU_NAO_POSITIVO",
                "sem_rag": {
                    "faithfulness": None,
                    "faithfulness_status": "NAO_APLICAVEL",
                    "answer_relevancy": None,
                    "context_recall": None,
                    "context_precision": None,
                },
                "com_rag": {
                    "faithfulness": None,
                    "answer_relevancy": None,
                    "context_recall": None,
                    "context_precision": None,
                },
            }
            casos_avaliados.append(copia)
            continue

        ids_positivos.add(copia["caso_id"])
        contextos = [
            str(ev.get("text", "")).strip()
            for ev in copia["com_rag"].get("evidencias", [])
            if str(ev.get("text", "")).strip()
        ]
        try:
            escores = avaliador.avaliar_par_positivo(
                pergunta=copia["com_rag"]["pergunta"],
                referencia=copia["com_rag"]["referencia"],
                resposta_sem_rag=copia["sem_rag"]["geracao"]["text"],
                resposta_com_rag=copia["com_rag"]["geracao"]["text"],
                contextos_com_rag=contextos,
            )
            copia["ragas"] = {
                "aplicavel": True,
                "erro_avaliador": None,
                "sem_rag": {
                    "faithfulness": None,
                    "faithfulness_status": "NAO_APLICAVEL",
                    "answer_relevancy": escores.sem_rag_answer_relevancy,
                    "context_recall": None,
                    "context_recall_status": "NAO_APLICAVEL",
                    "context_precision": None,
                    "context_precision_status": "NAO_APLICAVEL",
                },
                "com_rag": {
                    "faithfulness": escores.com_rag_faithfulness,
                    "answer_relevancy": escores.com_rag_answer_relevancy,
                    "context_recall": escores.com_rag_context_recall,
                    "context_precision": escores.com_rag_context_precision,
                },
            }
            sem_ar_vals.append(escores.sem_rag_answer_relevancy)
            com_faith_vals.append(escores.com_rag_faithfulness)
            com_ar_vals.append(escores.com_rag_answer_relevancy)
            com_cr_vals.append(escores.com_rag_context_recall)
            com_cp_vals.append(escores.com_rag_context_precision)
        except Exception as exc:
            erros_avaliador += 1
            copia["ragas"] = {
                "aplicavel": True,
                "erro_avaliador": str(exc),
                "sem_rag": {
                    "faithfulness": None,
                    "faithfulness_status": "NAO_APLICAVEL",
                    "answer_relevancy": None,
                    "context_recall": None,
                    "context_precision": None,
                },
                "com_rag": {
                    "faithfulness": None,
                    "answer_relevancy": None,
                    "context_recall": None,
                    "context_precision": None,
                },
            }
            sem_ar_vals.append(None)
            com_faith_vals.append(None)
            com_ar_vals.append(None)
            com_cr_vals.append(None)
            com_cp_vals.append(None)

        casos_avaliados.append(copia)

    esperados = len(ids_positivos)
    ragas_sem_rag = {
        "n_positivos_esperados": esperados,
        "faithfulness": None,
        "faithfulness_status": "NAO_APLICAVEL",
        "answer_relevancy": _media_completa(sem_ar_vals, esperados),
        "context_recall": None,
        "context_recall_status": "NAO_APLICAVEL",
        "context_precision": None,
        "context_precision_status": "NAO_APLICAVEL",
    }
    ragas_com_rag = {
        "n_positivos_esperados": esperados,
        "faithfulness": _media_completa(com_faith_vals, esperados),
        "answer_relevancy": _media_completa(com_ar_vals, esperados),
        "context_recall": _media_completa(com_cr_vals, esperados),
        "context_precision": _media_completa(com_cp_vals, esperados),
    }

    criterios = avaliar_limiares(
        {
            "faithfulness_ragas": ragas_com_rag["faithfulness"],
            "answer_relevancy_ragas": ragas_com_rag["answer_relevancy"],
            "context_recall_ragas": ragas_com_rag["context_recall"],
            "context_precision_ragas": ragas_com_rag["context_precision"],
        }
    )
    avaliacao_ragas_completa = (
        esperados > 0
        and erros_avaliador == 0
        and all(
            ragas_com_rag[k] is not None
            for k in ("faithfulness", "answer_relevancy", "context_recall", "context_precision")
        )
        and ragas_sem_rag["answer_relevancy"] is not None
    )
    sucesso_criterios_rag = avaliacao_ragas_completa and all(
        gate["status"] == "APROVADO" for gate in criterios.values()
    )

    factual_consolidado = (
        consolidar_auditoria_factual(auditoria_factual, ids_positivos)
        if auditoria_factual is not None
        else {"completa": False, "sem_rag": None, "com_rag": None}
    )

    if not avaliacao_ragas_completa:
        status_entregavel = "AVALIACAO_RAGAS_INCOMPLETA"
    elif not factual_consolidado["completa"]:
        status_entregavel = "RAGAS_CONCLUIDO_PENDENTE_AUDITORIA_FACTUAL"
    elif sucesso_criterios_rag:
        status_entregavel = "CONCLUIDO_APROVADO_ADR_0003"
    else:
        status_entregavel = "CONCLUIDO_REPROVADO_ADR_0003"

    resultado_final = dict(coleta)
    resultado_final.update(
        {
            "avaliado_em": datetime.now(UTC).isoformat(),
            "avaliacao_ragas_completa": avaliacao_ragas_completa,
            "erros_avaliador": erros_avaliador,
            "ragas_oficial": {
                "versao_ragas": "0.4.3",
                "evaluator_provider": avaliador.evaluator_provider,
                "evaluator_model": avaliador.evaluator_model,
                "embedding_model": avaliador.embedding_model,
                "sem_rag": ragas_sem_rag,
                "com_rag": ragas_com_rag,
            },
            "auditoria_factual": factual_consolidado,
            "criterios_adr_0003": criterios,
            "sucesso_criterios_rag": sucesso_criterios_rag,
            "status_entregavel": status_entregavel,
            "casos": casos_avaliados,
        }
    )
    resultado_final["protocolo"] = {
        **dict(coleta.get("protocolo", {})),
        "avaliador_ragas": f"ragas==0.4.3 ({avaliador.evaluator_model})",
        "embedding_ragas": avaliador.embedding_model,
    }
    resultado_final["sha256"] = {
        **dict(coleta.get("sha256", {})),
        "evals/runners/avaliar_ragas_oficial.py": hashlib.sha256(
            Path(__file__).resolve().read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
    }
    return resultado_final


def gerar_relatorio_ragas_markdown(relatorio: dict[str, Any]) -> str:
    ragas = relatorio["ragas_oficial"]
    sem = ragas["sem_rag"]
    com = ragas["com_rag"]
    factual = relatorio["auditoria_factual"]

    linhas = [
        "# Avaliação Oficial RAGAS e Auditoria Factual — Semana 3",
        "",
        f"- **Status do entregável:** `{relatorio['status_entregavel']}`",
        f"- **Tipo de execução:** `{relatorio['tipo_execucao']}`",
        f"- **Avaliador RAGAS (`ragas==0.4.3`):** `{ragas['evaluator_model']}` "
        f"(embeddings: `{ragas['embedding_model']}`)",
        f"- **Erros do avaliador:** `{relatorio['erros_avaliador']}`",
        f"- **Aprovação critérios ADR 0003:** `{relatorio['sucesso_criterios_rag']}`",
        "",
        "## 1. Métricas Oficiais RAGAS (Casos Positivos `PAR_LLM`)",
        "",
        "> `Faithfulness`, `Context Recall` e `Context Precision` exigem contexto recuperado "
        "e são registrados como `NAO_APLICAVEL` no braço sem RAG.",
        "",
        "| Métrica RAGAS | Braço A (Sem RAG) | Braço B (Com RAG) | Meta ADR 0003 | Status Gate |",
        "| --- | ---: | ---: | ---: | --- |",
        f"| `faithfulness` | {sem['faithfulness_status']} | {com['faithfulness']} | "
        f"{relatorio['criterios_adr_0003']['faithfulness_ragas']['minimo']} | "
        f"{relatorio['criterios_adr_0003']['faithfulness_ragas']['status']} |",
        f"| `answer_relevancy` | {sem['answer_relevancy']} | {com['answer_relevancy']} | "
        f"{relatorio['criterios_adr_0003']['answer_relevancy_ragas']['minimo']} | "
        f"{relatorio['criterios_adr_0003']['answer_relevancy_ragas']['status']} |",
        f"| `context_recall` | {sem['context_recall_status']} | {com['context_recall']} | "
        f"{relatorio['criterios_adr_0003']['context_recall_ragas']['minimo']} | "
        f"{relatorio['criterios_adr_0003']['context_recall_ragas']['status']} |",
        f"| `context_precision` | {sem['context_precision_status']} | {com['context_precision']} | "
        f"{relatorio['criterios_adr_0003']['context_precision_ragas']['minimo']} | "
        f"{relatorio['criterios_adr_0003']['context_precision_ragas']['status']} |",
        "",
        "## 2. Verificação Factual Independente (Denominadores Explícitos)",
        "",
    ]
    if factual["completa"]:
        f_sem = factual["sem_rag"]
        f_com = factual["com_rag"]
        linhas.extend(
            [
                "| Indicador Factual | Braço A (Sem RAG) | Braço B (Com RAG) |",
                "| --- | ---: | ---: |",
                f"| Total de afirmações auditadas | {f_sem['total_afirmacoes']} | "
                f"{f_com['total_afirmacoes']} |",
                f"| Afirmações corretas | {f_sem['afirmacoes_corretas']} | "
                f"{f_com['afirmacoes_corretas']} |",
                f"| Afirmações contraditas | {f_sem['afirmacoes_contraditas']} | "
                f"{f_com['afirmacoes_contraditas']} |",
                f"| Afirmações não verificáveis | {f_sem['afirmacoes_nao_verificaveis']} | "
                f"{f_com['afirmacoes_nao_verificaveis']} |",
                f"| Taxa de contradição por afirmação | "
                f"{f_sem['taxa_contradicao_por_afirmacao']} | "
                f"{f_com['taxa_contradicao_por_afirmacao']} |",
                f"| Taxa de erro factual total (contraditas + não verificáveis) | "
                f"{f_sem['taxa_erro_factual_por_afirmacao']} | "
                f"{f_com['taxa_erro_factual_por_afirmacao']} |",
            ]
        )
    else:
        linhas.append(
            "Auditoria factual humana **NAO CONCLUIDA**. Preencha `auditoria_factual_humana.json` "
            "no diretório da coleta (`revisado: true` em todos os casos positivos) e reexecute "
            "este avaliador para consolidar a taxa de alucinação factual sem regenerar respostas."
        )
    return "\n".join(linhas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--coleta-dir",
        type=Path,
        required=True,
        help="Diretório gerado por comparar_semana3.py contendo resultado.json",
    )
    parser.add_argument(
        "--evaluator-model",
        default="qwen2.5:14b",
        help="Modelo juiz para RAGAS (ex.: qwen2.5:14b)",
    )
    parser.add_argument(
        "--embedding-model",
        default="bge-m3",
        help="Modelo de embeddings para AnswerRelevancy no RAGAS (ex.: bge-m3)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434/v1",
        help="Endpoint OpenAI-compatível do provedor (default: http://localhost:11434/v1)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OPENAI_API_KEY", "ollama"),
        help="API key para o endpoint compatível (default: ollama)",
    )
    parser.add_argument(
        "--auditoria-humana",
        type=Path,
        help="Caminho opcional para auditoria_factual_humana.json preenchida",
    )
    args = parser.parse_args()

    coleta_dir = args.coleta_dir.resolve()
    caminho_resultado = coleta_dir / "resultado.json"
    if not caminho_resultado.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho_resultado}")

    coleta = json.loads(caminho_resultado.read_text(encoding="utf-8"))
    caminho_auditoria = args.auditoria_humana or (coleta_dir / "auditoria_factual_humana.json")
    if not caminho_auditoria.exists():
        template = gerar_template_auditoria_factual(coleta)
        caminho_auditoria.write_text(
            json.dumps(template, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    auditoria_dados = json.loads(caminho_auditoria.read_text(encoding="utf-8"))

    avaliador = OfficialRagasCollectionsEvaluator(
        evaluator_model=args.evaluator_model,
        embedding_model=args.embedding_model,
        base_url=args.base_url,
        api_key=args.api_key,
    )
    relatorio_final = avaliar_coleta_ragas(
        coleta,
        avaliador=avaliador,
        auditoria_factual=auditoria_dados,
    )

    tracker = MLflowExperimentTracker(raiz_repo=RAIZ)
    metricas_tracker: dict[str, float] = {
        "erros_avaliador": float(relatorio_final["erros_avaliador"]),
    }
    for chave, valor in relatorio_final["ragas_oficial"]["com_rag"].items():
        if isinstance(valor, (int, float)):
            metricas_tracker[f"com_rag_{chave}"] = float(valor)
    ar_sem = relatorio_final["ragas_oficial"]["sem_rag"]["answer_relevancy"]
    if isinstance(ar_sem, (int, float)):
        metricas_tracker["sem_rag_answer_relevancy"] = float(ar_sem)

    run = tracker.registrar_execucao(
        run_name="avaliacao_ragas_semana3",
        params={
            "evaluator_model": args.evaluator_model,
            "embedding_model": args.embedding_model,
            "dataset": relatorio_final["dataset"],
        },
        metrics=metricas_tracker,
        dataset_path=RAIZ / "evals/datasets" / relatorio_final["dataset"],
        extra_tags={"status_entregavel": relatorio_final["status_entregavel"]},
    )
    relatorio_final["ragas_tracking_run_id"] = run.run_id

    (coleta_dir / "avaliacao_ragas.json").write_text(
        json.dumps(relatorio_final, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (coleta_dir / "avaliacao_ragas.md").write_text(
        gerar_relatorio_ragas_markdown(relatorio_final),
        encoding="utf-8",
    )
    print(f"Avaliacao RAGAS salva em: {coleta_dir / 'avaliacao_ragas.json'}")
    print(f"Status entregavel: {relatorio_final['status_entregavel']}")
    if not relatorio_final["avaliacao_ragas_completa"]:
        return 1
    return 0 if relatorio_final["sucesso_criterios_rag"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
