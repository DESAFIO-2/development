"""Item 3: latência da API (braço C) medida no benchmark e lida pela consolidação."""

from __future__ import annotations

from typing import Any

from evals.runners.consolidar_quatro_bracos import gerar_markdown, montar_bracos
from evals.runners.ragas_runner import RAIZ, executar_benchmark, resumo_latencia


def test_mediana_e_p95_por_posto_mais_proximo() -> None:
    assert resumo_latencia([]) == (None, None)
    assert resumo_latencia([5.0]) == (5.0, 5.0)
    valores = [float(v) for v in range(1, 21)]  # 1..20
    assert resumo_latencia(valores) == (10.5, 19.0)
    assert resumo_latencia([3.0, 1.0, 2.0]) == (2.0, 3.0)


def test_benchmark_v2_mede_a_latencia_dos_positivos() -> None:
    metricas = executar_benchmark(RAIZ / "evals/datasets/golden_set_v2_consolidado.jsonl")
    assert metricas.n_positivos == 18
    assert metricas.latencia_mediana_ms_api is not None
    assert metricas.latencia_p95_ms_api is not None
    assert 0 < metricas.latencia_mediana_ms_api <= metricas.latencia_p95_ms_api


def _coleta() -> dict[str, Any]:
    caso = {
        "caso_id": "G1",
        "categoria": "POSITIVO",
        "status_par": "PAR_LLM",
        "sem_rag": {"geracao": {"latency_ms": 10000, "provider_metadata": None}},
        "com_rag": {"geracao": {"latency_ms": 22000, "provider_metadata": None}},
    }
    return {
        "dataset": "golden_set_v2_consolidado.jsonl",
        "avaliacao_ragas_completa": False,
        "metricas": {
            b: {"rota_correta_heuristica": 1.0, "n_positivos_pares_validos": 1}
            for b in ("sem_rag", "com_rag")
        },
        "casos": [caso],
    }


def test_consolidacao_mostra_latencia_e_n_do_braco_c() -> None:
    benchmark = {
        "dataset": "golden_set_v2_consolidado.jsonl",
        "acuracia_roteamento": 1.0,
        "n_positivos": 18,
        "latencia_mediana_ms_api": 6.3,
        "latencia_p95_ms_api": 12.6,
    }
    bracos = montar_bracos(padrao=_coleta(), benchmark=benchmark, blindada=None, seguranca=None)
    assert bracos["C"]["latencia_mediana_s"] == 0.0063
    assert bracos["C"]["n_rota"] == 18
    assert bracos["C"]["metas_atingidas"] == 0
    tabela = gerar_markdown(
        {"bracos": bracos, "escolha": {"braco": None, "motivo": "-", "ordem": []}}
    )
    assert "6.3 ms" in tabela
    assert "(n=18)" in tabela


def test_benchmark_antigo_sem_latencia_continua_nao_medido() -> None:
    benchmark = {"dataset": "golden_set_v2_consolidado.jsonl", "acuracia_roteamento": 1.0}
    bracos = montar_bracos(padrao=_coleta(), benchmark=benchmark, blindada=None, seguranca=None)
    assert bracos["C"]["latencia_mediana_s"] is None
    assert bracos["C"]["n_rota"] is None
