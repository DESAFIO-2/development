"""Registra no rastreador de experimentos os resultados das avaliações já produzidas.

Não roda modelo nem guardrail: lê os artefatos JSON que os runners gravam e manda as
métricas para o `MLflowExperimentTracker` (JSON em `evals/reports/mlflow_runs/` e, se o
pacote `mlflow` estiver no ambiente, também no MLflow em `evals/reports/mlflow.db`, ou em
`MLFLOW_TRACKING_URI`, se definido).

Assim os runners de avaliação não mudam (os hashes do manifesto continuam valendo) e dá
para registrar rodadas antigas a partir das evidências publicadas.

Artefatos aceitos:
  --guardrail     evals/reports/<--relatorio>.json (guardrail_runner.py)
  --seguranca     <SEG_DIR>/seguranca.json (suite_seguranca.py)
  --ragas         <RUN_DIR>/avaliacao_ragas.json (semana3_local.py), pode repetir
  --quatro-bracos <QUATRO_DIR>/quatro_bracos.json (consolidar_quatro_bracos.py)
  --semana4       <S4_RUN_DIR>/resultado.json (semana4_comparativo.py)

Registrar o mesmo artefato duas vezes não duplica: a execução é identificada pelo
SHA-256 do arquivo e pelo nome da execução.

Uso (raiz do repo):
  uv run --project backend python observability/registrar_avaliacoes.py \\
      --rotulo semana4-2026-11-17 --seguranca evals/reports/seguranca_2026-11-16/seguranca.json
"""

# ruff: noqa: E402
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from observability.mlflow_tracker import MLflowExperimentTracker

METRICAS_RAGAS = ("faithfulness", "answer_relevancy", "context_recall", "context_precision")
DIAGNOSTICOS = (
    "rota_correta_heuristica",
    "citacao_metadados_valida",
    "recall_chunks",
    "precision_chunks",
)
LADOS = ("sem_rag", "com_rag")


@dataclass(frozen=True)
class Registro:
    """Uma execução para o rastreador: o que identifica, o que configura e o que mede."""

    run_name: str
    params: dict[str, str]
    metrics: dict[str, float]
    tags: dict[str, str] = field(default_factory=dict)


def _numero(valor: Any) -> float | None:
    """Só aceita número de verdade; None, texto e booleano não viram métrica."""
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return None
    return float(valor)


def _metricas(pares: Iterable[tuple[str, Any]]) -> dict[str, float]:
    saida: dict[str, float] = {}
    for chave, valor in pares:
        numero = _numero(valor)
        if numero is not None:
            saida[chave] = numero
    return saida


def registros_guardrail(relatorio: dict[str, Any]) -> list[Registro]:
    dataset = str(relatorio["dataset"])
    # O holdout mede 3 alvos no mesmo dataset: o nome leva módulo e função para separar.
    modulo, _, funcao = str(relatorio["alvo"]).partition(":")
    alvo_curto = f"{modulo.rsplit('.', 1)[-1]}.{funcao}" if funcao else modulo
    return [
        Registro(
            run_name=f"guardrail_{Path(dataset).stem}_{alvo_curto}",
            params={"alvo": str(relatorio["alvo"]), "dataset": dataset},
            metrics=_metricas(
                (chave, relatorio.get(chave))
                for chave in (
                    "recall_bloqueio",
                    "taxa_falso_bloqueio",
                    "deviam_bloquear",
                    "bloqueados_corretamente",
                    "deviam_permitir",
                    "bloqueados_indevidamente",
                )
            ),
            tags={"suite": "guardrail", "executado_em": str(relatorio.get("executado_em", ""))},
        )
    ]


def registros_seguranca(relatorio: dict[str, Any]) -> list[Registro]:
    manifesto = relatorio.get("manifesto") or {}
    params = {
        "dataset": str(relatorio["dataset"]),
        "tipo_execucao": str(relatorio["tipo_execucao"]),
        "model": str(manifesto.get("model", "")),
    }
    registros = []
    for braco, dados in relatorio["bracos"].items():
        # Qualquer categoria da suíte (v1: injecao, pii, clinico; v2 soma injecao_indireta).
        taxas = {
            f"{categoria}_taxa": valor["aprovados"] / valor["total"]
            for categoria, valor in dados.items()
            if isinstance(valor, dict) and valor.get("total")
        }
        registros.append(
            Registro(
                run_name=f"seguranca_{braco}",
                params=params | {"braco": braco},
                metrics=taxas
                | {
                    "falhas": float(len(dados["falhas"])),
                    "invalidos": float(len(dados["invalidos"])),
                    "aprovado_seguranca": 1.0 if dados["status"] == "APROVADO" else 0.0,
                },
                tags={
                    "suite": "seguranca",
                    "status": str(dados["status"]),
                    "executado_em": str(relatorio.get("executado_em", "")),
                },
            )
        )
    return registros


def registros_ragas(relatorio: dict[str, Any]) -> list[Registro]:
    oficial = relatorio.get("ragas_oficial") or {}
    diagnosticos = relatorio.get("metricas") or {}
    variante = str(relatorio.get("variante") or "padrao")
    metricas: dict[str, float] = {}
    for lado in LADOS:
        metricas |= _metricas(
            (f"{lado}_{nome}", (oficial.get(lado) or {}).get(nome)) for nome in METRICAS_RAGAS
        )
        metricas |= _metricas(
            (f"{lado}_{nome}", (diagnosticos.get(lado) or {}).get(nome)) for nome in DIAGNOSTICOS
        )
    metricas["avaliacao_ragas_completa"] = 1.0 if relatorio.get("avaliacao_ragas_completa") else 0.0
    return [
        Registro(
            run_name=f"ragas_{variante}",
            params={
                "dataset": str(relatorio.get("dataset", "")),
                "variante": variante,
                "evaluator_model": str(oficial.get("evaluator_model", "")),
                "embedding_model": str(oficial.get("embedding_model", "")),
                "versao_ragas": str(oficial.get("versao_ragas", "")),
                "top_k": str(relatorio.get("top_k", "")),
            },
            metrics=metricas,
            tags={
                "suite": "ragas",
                "status_entregavel": str(relatorio.get("status_entregavel", "")),
                "executado_em": str(relatorio.get("avaliado_em", "")),
            },
        )
    ]


def registros_quatro_bracos(relatorio: dict[str, Any]) -> list[Registro]:
    escolhido = (relatorio.get("escolha") or {}).get("braco")
    registros = []
    for letra, dados in relatorio["bracos"].items():
        registros.append(
            Registro(
                run_name=f"quatro_bracos_{letra}",
                params={
                    "braco": letra,
                    "nome": str(dados.get("nome", "")),
                    "dataset": str(relatorio.get("dataset", "")),
                    "metodo_rota": str(dados.get("metodo_rota")),
                },
                metrics=_metricas(
                    (chave, dados.get(chave))
                    for chave in ("acerto_rota", "metas_atingidas", "latencia_mediana_s")
                )
                | {
                    "aprovado_seguranca": 1.0 if dados.get("seguranca") == "APROVADO" else 0.0,
                    "escolhido": 1.0 if escolhido == letra else 0.0,
                },
                tags={
                    "suite": "quatro_bracos",
                    "seguranca": str(dados.get("seguranca", "")),
                    "braco_escolhido": str(escolhido),
                    "executado_em": str(relatorio.get("executado_em", "")),
                },
            )
        )
    return registros


def registros_semana4(relatorio: dict[str, Any]) -> list[Registro]:
    """Um registro por modelo do comparativo multiagente (Qwen2.5 7B x 14B)."""
    registros = []
    for modelo, resumo in (relatorio.get("resumos") or {}).items():
        metricas = _metricas(
            (chave, resumo.get(chave))
            for chave in (
                "casos_executados",
                "gerados",
                "abstencoes",
                "bloqueados",
                "falhas_ou_rejeicoes",
                "mediana_wall_ms",
                "p95_wall_ms",
                "mediana_geracao_ms",
            )
        )
        metricas["dentro_meta_rnf04_8s"] = 1.0 if resumo.get("dentro_meta_rnf04_8s") else 0.0
        registros.append(
            Registro(
                run_name=f"semana4_{modelo}",
                params={
                    "model": str(modelo),
                    "prompt_version": str(relatorio.get("prompt_version", "")),
                    "casos_planejados": str(relatorio.get("casos_planejados", "")),
                },
                metrics=metricas,
                tags={
                    "suite": "semana4_agentes",
                    "status_cientifico": str(relatorio.get("status_cientifico", "")),
                    "execucao_real": str(relatorio.get("execucao_real", "")),
                    "executado_em": str(relatorio.get("timestamp_utc", "")),
                },
            )
        )
    return registros


EXTRATORES = {
    "guardrail": registros_guardrail,
    "seguranca": registros_seguranca,
    "ragas": registros_ragas,
    "quatro_bracos": registros_quatro_bracos,
    "semana4": registros_semana4,
}


def ja_registrados(pasta_runs: Path) -> set[tuple[str, str]]:
    """Pares (sha256 do artefato, nome da execução) já presentes no JSON local."""
    vistos: set[tuple[str, str]] = set()
    for arquivo in sorted(pasta_runs.glob("run_*.json")):
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        sha = (dados.get("tags") or {}).get("artefato_sha256")
        if sha:
            vistos.add((sha, str(dados.get("run_name"))))
    return vistos


def registrar(
    tracker: MLflowExperimentTracker, tipo: str, caminho: Path, rotulo: str
) -> tuple[int, int]:
    """Registra um artefato. Devolve (novas execuções, execuções puladas por já existirem)."""
    bruto = caminho.read_bytes()
    sha = hashlib.sha256(bruto).hexdigest()
    relatorio = json.loads(bruto.decode("utf-8"))
    vistos = ja_registrados(tracker.pasta_runs)
    novos = pulados = 0
    for registro in EXTRATORES[tipo](relatorio):
        if (sha, registro.run_name) in vistos:
            pulados += 1
            continue
        tracker.registrar_execucao(
            run_name=registro.run_name,
            params=registro.params,
            metrics=registro.metrics,
            extra_tags=registro.tags
            | {"rotulo": rotulo, "artefato": caminho.name, "artefato_sha256": sha},
        )
        novos += 1
    return novos, pulados


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rotulo", required=True, help="Nome da rodada, ex.: semana4-2026-11-17")
    parser.add_argument("--guardrail", type=Path, action="append", default=[])
    parser.add_argument("--seguranca", type=Path, action="append", default=[])
    parser.add_argument("--ragas", type=Path, action="append", default=[])
    parser.add_argument("--quatro-bracos", type=Path, action="append", default=[])
    parser.add_argument("--semana4", type=Path, action="append", default=[])
    args = parser.parse_args()
    pedidos = [
        (tipo, caminho)
        for tipo, caminhos in (
            ("guardrail", args.guardrail),
            ("seguranca", args.seguranca),
            ("ragas", args.ragas),
            ("quatro_bracos", args.quatro_bracos),
            ("semana4", args.semana4),
        )
        for caminho in caminhos
    ]
    if not pedidos:
        parser.error("Informe pelo menos um artefato (--guardrail, --seguranca, ...)")
    faltando = [str(caminho) for _, caminho in pedidos if not caminho.exists()]
    if faltando:
        parser.error(f"Artefato não encontrado: {', '.join(faltando)}")
    tracker = MLflowExperimentTracker(raiz_repo=RAIZ)
    for tipo, caminho in pedidos:
        novos, pulados = registrar(tracker, tipo, caminho, args.rotulo)
        print(f"{tipo}: {caminho} -> {novos} execuções novas, {pulados} já registradas")
    print(f"Registros em {tracker.pasta_runs.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
