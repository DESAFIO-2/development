"""Consolidação dos quatro braços e regra de escolha."""

from __future__ import annotations

from typing import Any

import pytest
from evals.runners.consolidar_quatro_bracos import escolher, montar_bracos


def _caso(caso_id: str, lat_sem: float, lat_com: float, **com_meta: Any) -> dict[str, Any]:
    return {
        "caso_id": caso_id,
        "categoria": "POSITIVO",
        "status_par": "PAR_LLM",
        "sem_rag": {"geracao": {"latency_ms": lat_sem, "provider_metadata": None}},
        "com_rag": {"geracao": {"latency_ms": lat_com, "provider_metadata": com_meta or None}},
    }


def _coleta(rota_com: float = 1.0, faith: float = 0.95, **com_meta: Any) -> dict[str, Any]:
    return {
        "dataset": "golden_set_v2_consolidado.jsonl",
        "manifesto_experimento": {"dataset_sha256": "x", "provider": "ollama", "model": "m"},
        "protocolo": {"prompt_version": "semana3-v2"},
        "avaliacao_ragas_completa": True,
        "metricas": {
            "sem_rag": {"rota_correta_heuristica": 0.4, "n_positivos_pares_validos": 2},
            "com_rag": {"rota_correta_heuristica": rota_com, "n_positivos_pares_validos": 2},
        },
        "ragas_oficial": {
            "sem_rag": {"answer_relevancy": 0.3},
            "com_rag": {
                "faithfulness": faith,
                "answer_relevancy": 0.9,
                "context_recall": 0.95,
                "context_precision": 0.9,
            },
        },
        "casos": [
            _caso("G1", 1000, 20000, **com_meta),
            _caso("G2", 3000, 30000),
            {**_caso("G3", 1, 1), "categoria": "BLOQUEIO", "status_par": "CONTROLE"},
        ],
    }


def _seguranca(**status: str) -> dict[str, Any]:
    chaves = {
        "A": "A_llm_sem_rag",
        "B": "B_llm_com_rag",
        "C": "C_rag_sem_llm",
        "D": "D_llm_rag_blindado",
    }
    return {
        "tipo_execucao": "COLETA_REAL",
        "bracos": {chaves[k]: {"status": v, "falhas": []} for k, v in status.items()},
    }


BENCHMARK = {"dataset": "golden_set_v2_consolidado.jsonl", "acuracia_roteamento": 1.0}


def test_metricas_e_latencia_mediana_so_dos_positivos_llm() -> None:
    bracos = montar_bracos(padrao=_coleta(), benchmark=None, blindada=None, seguranca=None)
    assert bracos["A"]["latencia_mediana_s"] == 2.0
    assert bracos["B"]["latencia_mediana_s"] == 25.0
    assert bracos["B"]["metas_atingidas"] == 4
    assert bracos["A"]["metas_atingidas"] == 0
    assert bracos["C"]["seguranca"] == "NAO_AVALIADO"
    assert bracos["D"]["acerto_rota"] is None


def test_seguranca_elimina_antes_de_qualquer_outro_criterio() -> None:
    bracos = montar_bracos(
        padrao=_coleta(),
        benchmark=BENCHMARK,
        blindada=_coleta(faith=0.5, seguranca_camada="saida"),
        seguranca=_seguranca(A="APROVADO", B="ELIMINADO", C="ELIMINADO", D="APROVADO"),
    )
    escolha = escolher(bracos)
    assert escolha["ordem"] == ["D", "A"]
    assert escolha["braco"] == "D"
    assert bracos["D"]["metas_atingidas"] == 3
    assert bracos["D"]["bloqueios_em_positivos"] == ["G1"]


def test_empate_em_rota_decide_por_metas_e_braco_sem_latencia_fica_por_ultimo() -> None:
    bracos = montar_bracos(
        padrao=_coleta(),
        benchmark=BENCHMARK,
        blindada=None,
        seguranca=_seguranca(B="APROVADO", C="APROVADO"),
    )
    assert escolher(bracos)["ordem"] == ["B", "C"]


def test_suite_sintetica_nao_vale_para_escolha() -> None:
    seguranca = {**_seguranca(A="APROVADO", B="APROVADO"), "tipo_execucao": "SINTETICA"}
    bracos = montar_bracos(padrao=_coleta(), benchmark=None, blindada=None, seguranca=seguranca)
    assert escolher(bracos)["braco"] is None


def test_coleta_blindada_de_outro_modelo_nao_e_comparavel() -> None:
    blindada = _coleta()
    blindada["manifesto_experimento"] = {**blindada["manifesto_experimento"], "model": "outro"}
    with pytest.raises(ValueError, match="model"):
        montar_bracos(padrao=_coleta(), benchmark=None, blindada=blindada, seguranca=None)


def test_ragas_incompleto_nao_conta_meta() -> None:
    padrao = {**_coleta(), "avaliacao_ragas_completa": False}
    bracos = montar_bracos(padrao=padrao, benchmark=None, blindada=None, seguranca=None)
    assert bracos["B"]["metas_atingidas"] == 0
