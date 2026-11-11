"""Estágio 2 do comparativo Semana 3: Avaliação oficial RAGAS (0.4.3) e auditoria factual."""

# ruff: noqa: E402
from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[2]
for _cam in (RAIZ, RAIZ / "backend"):
    if str(_cam) not in sys.path:
        sys.path.insert(0, str(_cam))

from evals.runners.artifacts import atomic_json, digest, read_json
from evals.runners.factual_audit import consolidar_auditoria_factual


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
    if isinstance(valor, bool):
        raise ValueError("Booleano não é escore")
    numero = float(valor)
    if not math.isfinite(numero) or numero < 0.0 or numero > 1.0:
        raise ValueError(f"Escore RAGAS inválido ou não finito em {nome}: {valor!r}")
    return numero


def _media_completa(valores: list[float | None], esperado: int) -> float | None:
    if esperado == 0 or len(valores) != esperado or any(v is None for v in valores):
        return None
    finitos = [float(v) for v in valores if v is not None]
    return sum(finitos) / len(finitos)


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
        metric_cache: Path | None = None,
        timeout: float = 180.0,
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

        self._runner = asyncio.Runner()
        self._metric_cache = metric_cache
        httpx = importlib.import_module("httpx")

        async def request_hook(request: Any) -> None:
            request.extensions["eval_started"] = time.perf_counter()

        async def response_hook(response: Any) -> None:
            if metric_cache is None:
                return
            await response.aread()
            atomic_json(
                metric_cache.parent / "http" / f"{uuid4().hex}.json",
                {
                    "endpoint": response.request.url.path,
                    "model": json.loads(response.request.content).get("model"),
                    "timestamp": datetime.now(UTC).isoformat(),
                    "latency_seconds": time.perf_counter()
                    - response.request.extensions["eval_started"],
                    "status": response.status_code,
                    "request_body": json.loads(response.request.content),
                    "response_body": response.text,
                },
            )

        async_client = openai_mod.AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
            max_retries=0,
            http_client=httpx.AsyncClient(
                event_hooks={"request": [request_hook], "response": [response_hook]}
            ),
        )
        self._client = async_client
        llm = ragas_llms.llm_factory(
            self.evaluator_model,
            provider="openai",
            client=async_client,
            temperature=0.0,
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

    async def _score(self, name: str, metric: Any, **kwargs: Any) -> Any:
        from types import SimpleNamespace

        path = self._metric_cache / f"{digest([name, kwargs])}.json" if self._metric_cache else None
        if path and path.exists():
            saved = read_json(path)
            if digest(saved["payload"]) != saved["sha256"]:
                raise ValueError("Checkpoint de métrica corrompido")
            return SimpleNamespace(value=saved["payload"]["value"])
        start = time.perf_counter()
        score = await metric.ascore(**kwargs)
        value = _validar_escore_finito(name, score.value)
        if path:
            payload = {
                "metric": name,
                "input": kwargs,
                "value": value,
                "latency_seconds": time.perf_counter() - start,
            }
            atomic_json(path, {"payload": payload, "sha256": digest(payload)})
        return SimpleNamespace(value=value)

    def close(self) -> None:
        self._runner.run(self._client.close())
        self._runner.close()

    async def _avaliar_async(
        self,
        *,
        pergunta: str,
        referencia: str,
        resposta_sem_rag: str,
        resposta_com_rag: str,
        contextos_com_rag: list[str],
    ) -> EscoresCasoRagas:
        ar_sem = await self._score(
            "answer_relevancy",
            self._answer_relevancy,
            user_input=pergunta,
            response=resposta_sem_rag,
        )
        faith_com = await self._score(
            "faithfulness",
            self._faithfulness,
            user_input=pergunta,
            response=resposta_com_rag,
            retrieved_contexts=contextos_com_rag,
        )
        ar_com = await self._score(
            "answer_relevancy",
            self._answer_relevancy,
            user_input=pergunta,
            response=resposta_com_rag,
        )
        cr_com = await self._score(
            "context_recall",
            self._context_recall,
            user_input=pergunta,
            retrieved_contexts=contextos_com_rag,
            reference=referencia,
        )
        cp_com = await self._score(
            "context_precision",
            self._context_precision,
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
        return self._runner.run(
            self._avaliar_async(
                pergunta=pergunta,
                referencia=referencia,
                resposta_sem_rag=resposta_sem_rag,
                resposta_com_rag=resposta_com_rag,
                contextos_com_rag=contextos_com_rag,
            )
        )


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

    casos = coleta.get("casos", [])
    if (
        not casos
        or coleta.get("total_casos") != len(casos)
        or len({c["caso_id"] for c in casos}) != len(casos)
        or any(c["status_par"] not in {"PAR_LLM", "CONTROLE_DETERMINISTICO"} for c in casos)
    ):
        raise ValueError("Coleta inconsistente: contagem, IDs ou status inválidos")
    for caso in casos:
        for braco in ("sem_rag", "com_rag"):
            geracao = caso[braco]["geracao"]
            if geracao.get("error_code") or not geracao.get("text", "").strip():
                raise ValueError("Coleta contém resposta vazia ou falha de provedor")

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
        consolidar_auditoria_factual(auditoria_factual, coleta)
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
                f"| Proporção não confirmada (contradita ou não verificável) | "
                f"{f_sem['taxa_afirmacoes_nao_confirmadas']} | "
                f"{f_com['taxa_afirmacoes_nao_confirmadas']} |",
            ]
        )
        linhas.extend(
            [
                "",
                "Os totais acima incluem controles; comparação por origem abaixo.",
                "",
                "| Origem | Braço | Respostas | Afirmações | Contradições | Não verificáveis |",
                "| --- | --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for origem, bracos in factual["por_origem"].items():
            for braco, valores in bracos.items():
                linhas.append(
                    f"| {origem} | {braco} | {valores['total_casos_avaliados']} | "
                    f"{valores['total_afirmacoes']} | {valores['afirmacoes_contraditas']} | "
                    f"{valores['afirmacoes_nao_verificaveis']} |"
                )
    else:
        linhas.append(
            "Auditoria factual humana **NAO CONCLUIDA**. Preencha `auditoria_factual_humana.json` "
            "no diretório da coleta. Execute --consolidate-only "
            "para consolidar sem novas chamadas ao juiz."
        )
    linhas.extend(
        [
            "",
            "## Diferenças pareadas de Answer Relevancy",
            "",
            "| Caso | Sem RAG | Com RAG | Diferença (com − sem) |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for caso in relatorio["casos"]:
        metricas = caso["ragas"]
        if metricas["aplicavel"] and not metricas.get("erro_avaliador"):
            a = metricas["sem_rag"]["answer_relevancy"]
            b = metricas["com_rag"]["answer_relevancy"]
            linhas.append(f"| {caso['caso_id']} | {a:.4f} | {b:.4f} | {b - a:.4f} |")
    linhas.extend(
        [
            "",
            "Limitações: desenvolvimento/regressão, sem teste independente de generalização. "
            "Gerador e juiz iguais podem compartilhar vieses. Revisão identificada, não cega. "
            "Faithfulness não comprova verdade factual nem garante ausência de alucinações.",
        ]
    )
    return "\n".join(linhas) + "\n"


def main() -> int:
    from evals.runners.evaluation_cli import main as executar

    return executar()


if __name__ == "__main__":
    raise SystemExit(main())
