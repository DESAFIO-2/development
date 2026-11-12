"""Métricas determinísticas de recuperação (só IDs, sem juiz LLM)."""

from __future__ import annotations

import math

import pytest
from evals.runners.ragas_runner import metricas_de_ranking


def test_um_relevante_na_posicao_2() -> None:
    m = metricas_de_ranking(["CHK-X", "CHK-A", "CHK-Y"], {"CHK-A"})
    assert m.hit is True
    assert m.precision_at_1 == 0.0
    assert m.r_precision == 0.0
    assert m.reciprocal_rank == 0.5
    assert m.recall == 1.0
    assert m.precision_at_k == pytest.approx(1 / 3)
    assert m.ndcg_at_k == pytest.approx(1 / math.log2(3))


def test_ranking_perfeito_com_dois_relevantes() -> None:
    m = metricas_de_ranking(["CHK-A", "CHK-B", "CHK-X"], {"CHK-A", "CHK-B"})
    assert m.precision_at_1 == 1.0
    assert m.r_precision == 1.0
    assert m.ndcg_at_k == pytest.approx(1.0)
    assert m.precision_at_k == pytest.approx(2 / 3)
    assert m.teto_precision_at_k == pytest.approx(2 / 3)


def test_teto_de_precision_at_3_com_um_relevante() -> None:
    m = metricas_de_ranking(["CHK-A", "CHK-X", "CHK-Y"], {"CHK-A"})
    assert m.precision_at_k == pytest.approx(1 / 3)
    assert m.teto_precision_at_k == pytest.approx(1 / 3)


def test_nenhum_relevante_recuperado() -> None:
    m = metricas_de_ranking(["CHK-X", "CHK-Y", "CHK-Z"], {"CHK-A"})
    assert m.hit is False
    assert m.reciprocal_rank == 0.0
    assert m.ndcg_at_k == 0.0
    assert m.recall == 0.0


def test_lista_vazia_de_recuperados() -> None:
    m = metricas_de_ranking([], {"CHK-A"})
    assert m.precision_at_1 == 0.0
    assert m.precision_at_k == 0.0


def test_caso_sem_relevantes_falha_explicitamente() -> None:
    with pytest.raises(ValueError):
        metricas_de_ranking(["CHK-A"], set())
