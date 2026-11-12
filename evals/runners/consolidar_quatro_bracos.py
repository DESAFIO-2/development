"""Tabela única dos quatro braços da semana 3 e escolha do melhor por regra fixa.

Não roda modelo nem recalcula RAGAS: só lê artefatos já produzidos.

- A e B: `avaliacao_ragas.json` da coleta padrão (`--coleta-padrao`).
- C: relatório do `make benchmark` no Golden Set v2 (`--benchmark`).
- D: `avaliacao_ragas.json` da coleta `--variante blindado` (`--coleta-blindada`).
- Segurança: `seguranca.json` da suíte (`--seguranca`).

Regra de escolha (definida antes de ver os números do braço D):
1. Segurança elimina: só concorre braço com status APROVADO na suíte.
2. Maior acerto de rota nos positivos do Golden Set v2.
3. Mais metas do ADR 0003 atingidas (braço sem RAGAS conta 0).
4. Menor latência mediana (braço sem latência medida fica por último).

Artefato ausente ou incompleto vira NAO_AVALIADO, nunca aprovação (diretrizes, Regra 5).
"""

# ruff: noqa: E402
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "backend"))

from evals.runners.artifacts import atomic_json, atomic_text
from evals.runners.comparar_semana3 import avaliar_limiares

NOMES = {
    "A": "LLM sem RAG",
    "B": "LLM com RAG",
    "C": "RAG sem LLM (API determinística)",
    "D": "LLM com RAG blindado",
}
_CHAVES_SUITE = {
    "A": "A_llm_sem_rag",
    "B": "B_llm_com_rag",
    "C": "C_rag_sem_llm",
    "D": "D_llm_rag_blindado",
}


def _ler(caminho: Path | None) -> dict[str, Any] | None:
    if caminho is None or not caminho.exists():
        return None
    dados: dict[str, Any] = json.loads(caminho.read_text(encoding="utf-8"))
    return dados


def _positivos_llm(avaliacao: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        caso
        for caso in avaliacao["casos"]
        if caso["categoria"] == "POSITIVO" and caso["status_par"] == "PAR_LLM"
    ]


def _latencia_mediana_s(avaliacao: dict[str, Any], braco: str) -> float | None:
    latencias = [c[braco]["geracao"]["latency_ms"] for c in _positivos_llm(avaliacao)]
    return round(statistics.median(latencias) / 1000, 2) if latencias else None


def _metas(avaliacao: dict[str, Any], braco: str) -> dict[str, dict[str, Any]]:
    ragas = (avaliacao.get("ragas_oficial") or {}).get(braco) or {}
    if not avaliacao.get("avaliacao_ragas_completa"):
        ragas = {}
    return avaliar_limiares(
        {
            "faithfulness_ragas": ragas.get("faithfulness"),
            "answer_relevancy_ragas": ragas.get("answer_relevancy"),
            "context_recall_ragas": ragas.get("context_recall"),
            "context_precision_ragas": ragas.get("context_precision"),
        }
    )


def _braco_llm(avaliacao: dict[str, Any], braco: str) -> dict[str, Any]:
    metas = _metas(avaliacao, braco)
    diagnosticos = avaliacao["metricas"][braco]
    return {
        "acerto_rota": diagnosticos["rota_correta_heuristica"],
        "n_rota": diagnosticos["n_positivos_pares_validos"],
        "metodo_rota": "heuristica_sobre_texto_gerado",
        "metas_adr_0003": metas,
        "metas_atingidas": sum(m["status"] == "APROVADO" for m in metas.values()),
        "latencia_mediana_s": _latencia_mediana_s(avaliacao, braco),
    }


def _nao_avaliado(motivo: str) -> dict[str, Any]:
    return {
        "acerto_rota": None,
        "n_rota": 0,
        "metodo_rota": None,
        "metas_adr_0003": avaliar_limiares({}),
        "metas_atingidas": 0,
        "latencia_mediana_s": None,
        "observacao": motivo,
    }


def _bloqueios_em_positivos(avaliacao: dict[str, Any]) -> list[str]:
    """Positivos em que a blindagem trocou ou barrou a resposta do braço com RAG."""
    bloqueados = []
    for caso in avaliacao["casos"]:
        geracao = caso["com_rag"]["geracao"]
        camada = (geracao.get("provider_metadata") or {}).get("seguranca_camada")
        if caso["categoria"] == "POSITIVO" and camada in {"entrada", "saida"}:
            bloqueados.append(caso["caso_id"])
    return bloqueados


def _conferir_comparabilidade(padrao: dict[str, Any], blindada: dict[str, Any]) -> None:
    """D só é comparável com B se dataset, modelo e prompt forem os mesmos."""
    for chave in ("dataset_sha256", "provider", "model"):
        if padrao["manifesto_experimento"].get(chave) != blindada["manifesto_experimento"].get(
            chave
        ):
            raise ValueError(f"Coleta blindada não é comparável com a padrão: {chave} difere")
    if padrao["protocolo"]["prompt_version"] != blindada["protocolo"]["prompt_version"]:
        raise ValueError("Coleta blindada não é comparável com a padrão: prompt difere")


def montar_bracos(
    *,
    padrao: dict[str, Any],
    benchmark: dict[str, Any] | None,
    blindada: dict[str, Any] | None,
    seguranca: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    bracos = {"A": _braco_llm(padrao, "sem_rag"), "B": _braco_llm(padrao, "com_rag")}
    if benchmark is None:
        bracos["C"] = _nao_avaliado("benchmark do Golden Set v2 não encontrado")
    else:
        if benchmark.get("dataset") != padrao["dataset"]:
            raise ValueError("Benchmark do braço C foi rodado em outro dataset")
        bracos["C"] = {
            **_nao_avaliado("sem RAGAS e sem latência medida (API determinística)"),
            "acerto_rota": benchmark["acuracia_roteamento"],
            "n_rota": None,
            "metodo_rota": "rota_estruturada_da_api",
        }
    if blindada is None:
        bracos["D"] = _nao_avaliado("coleta blindada ainda não rodada")
    else:
        _conferir_comparabilidade(padrao, blindada)
        bracos["D"] = {
            **_braco_llm(blindada, "com_rag"),
            "bloqueios_em_positivos": _bloqueios_em_positivos(blindada),
        }
    for letra, braco in bracos.items():
        suite = ((seguranca or {}).get("bracos") or {}).get(_CHAVES_SUITE[letra])
        braco["nome"] = NOMES[letra]
        braco["seguranca"] = suite["status"] if suite else "NAO_AVALIADO"
        braco["seguranca_falhas"] = suite["falhas"] if suite else []
    if seguranca is not None and seguranca.get("tipo_execucao") != "COLETA_REAL":
        for braco in bracos.values():
            braco["seguranca"] = "NAO_AVALIADO"
            braco["observacao_seguranca"] = "suíte sintética não vale para a escolha"
    return bracos


def escolher(bracos: dict[str, dict[str, Any]]) -> dict[str, Any]:
    elegiveis = [letra for letra, b in bracos.items() if b["seguranca"] == "APROVADO"]
    if not elegiveis:
        return {
            "braco": None,
            "motivo": "Nenhum braço aprovado na suíte de segurança (eliminados ou não avaliados).",
            "ordem": [],
        }

    def chave(letra: str) -> tuple[float, int, int, float]:
        b = bracos[letra]
        rota = b["acerto_rota"] if b["acerto_rota"] is not None else -1.0
        latencia = b["latencia_mediana_s"]
        return (-rota, -b["metas_atingidas"], latencia is None, latencia or 0.0)

    ordem = sorted(elegiveis, key=chave)
    return {
        "braco": ordem[0],
        "motivo": "Primeiro na ordem: segurança, rota, metas do ADR 0003 e latência.",
        "ordem": ordem,
    }


def _formatar(valor: float | None, sufixo: str = "") -> str:
    return "não medido" if valor is None else f"{valor:.2f}{sufixo}"


def _percentual(valor: float | None) -> str:
    return "não medido" if valor is None else f"{valor:.2%}"


def gerar_markdown(relatorio: dict[str, Any]) -> str:
    linhas = [
        "# Comparativo dos quatro braços (semana 3)",
        "",
        "| Braço | Segurança | Acerto de rota | Metas ADR 0003 | Latência mediana |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for letra, b in relatorio["bracos"].items():
        n = f" (n={b['n_rota']})" if b["n_rota"] else ""
        linhas.append(
            f"| {letra}. {b['nome']} | {b['seguranca']} | {_percentual(b['acerto_rota'])}{n} "
            f"| {b['metas_atingidas']}/4 | {_formatar(b['latencia_mediana_s'], ' s')} |"
        )
    escolha = relatorio["escolha"]
    linhas.extend(
        [
            "",
            f"**Braço escolhido:** {escolha['braco'] or 'nenhum'}. {escolha['motivo']}",
            "",
            "Regra: 1) segurança elimina; 2) maior acerto de rota; 3) mais metas do ADR 0003 "
            "(sem RAGAS conta 0); 4) menor latência mediana (sem medida fica por último).",
            "",
            "Limitações: acerto de rota de A, B e D é heurística sobre o texto, e o de C vem "
            "da rota estruturada da API; o mesmo modelo gera e julga no RAGAS; os 22 casos "
            "são de desenvolvimento; a suíte de segurança é sintética e escrita junto com as "
            "regras; a auditoria factual humana continua pendente.",
        ]
    )
    bloqueios = relatorio["bracos"]["D"].get("bloqueios_em_positivos")
    if bloqueios:
        linhas.append(
            f"\nBraço D trocou ou barrou a resposta em {len(bloqueios)} positivo(s): "
            f"{', '.join(bloqueios)}."
        )
    return "\n".join(linhas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coleta-padrao", type=Path, required=True)
    parser.add_argument("--coleta-blindada", type=Path)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=RAIZ / "evals/reports/rag_benchmark_golden_set_v2_consolidado.json",
    )
    parser.add_argument(
        "--seguranca", type=Path, default=RAIZ / "evals/reports/seguranca_variantes/seguranca.json"
    )
    parser.add_argument("--saida-dir", type=Path, default=RAIZ / "evals/reports/quatro_bracos")
    args = parser.parse_args()
    padrao = _ler(args.coleta_padrao / "avaliacao_ragas.json")
    if padrao is None:
        parser.error(f"avaliacao_ragas.json não encontrado em {args.coleta_padrao}")
    blindada = _ler(args.coleta_blindada / "avaliacao_ragas.json") if args.coleta_blindada else None
    bracos = montar_bracos(
        padrao=padrao,
        benchmark=_ler(args.benchmark),
        blindada=blindada,
        seguranca=_ler(args.seguranca),
    )
    relatorio = {
        "schema_version": "quatro-bracos-v1",
        "executado_em": datetime.now(UTC).isoformat(),
        "dataset": padrao["dataset"],
        "bracos": bracos,
        "escolha": escolher(bracos),
    }
    args.saida_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(args.saida_dir / "quatro_bracos.json", relatorio)
    markdown = gerar_markdown(relatorio)
    atomic_text(args.saida_dir / "quatro_bracos.md", markdown)
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
