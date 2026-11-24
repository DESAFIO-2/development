"""Testes unitários dos gates e verificações do runner multimodal (Semana 5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from evals.runners import avaliar_multimodal


def test_verificar_cenario_cobra_evidencias_e_termos_normativos() -> None:
    base_body = {
        "sucesso": True,
        "requer_confirmacao_usuario": False,
        "resultado_agentes": {
            "citacoes": ["[Fonte: CHK-1]"],
            "resposta_adicional": "Polo de Alto Custo / CEAF em Ceilândia.",
            "card": {
                "regiao_administrativa": "Ceilândia",
                "itens_auditados": [
                    {"via_retirada": "FARMACIA_POPULAR"},
                    {"via_retirada": "UBS_REME_DF"},
                    {"via_retirada": "FARMACIA_ALTO_CUSTO"},
                ],
            },
        },
    }
    ok, _ = avaliar_multimodal._verificar_cenario("dona_helena_pdf_e_voz", base_body)
    assert ok

    sem_citacao = json.loads(json.dumps(base_body))
    sem_citacao["resultado_agentes"]["citacoes"] = []
    ok_sem, _ = avaliar_multimodal._verificar_cenario("dona_helena_pdf_e_voz", sem_citacao)
    assert not ok_sem


def test_runner_multimodal_reprova_quando_rnf04_falha(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out_dir = tmp_path / "out_rnf04"
    monkeypatch.setattr(avaliar_multimodal, "LIMITE_P95_RNF04_MS", 0.0)
    monkeypatch.setattr(
        sys,
        "argv",
        ["avaliar_multimodal.py", "--synthetic-smoke", "--out-dir", str(out_dir)],
    )
    codigo = avaliar_multimodal.main()
    assert codigo == 1
    relatorio = json.loads((out_dir / "resultado.json").read_text(encoding="utf-8"))
    assert relatorio["gates"]["funcional_e_lgpd"] == "APROVADO"
    assert relatorio["gates"]["rnf04_p95_8000ms"] == "REPROVADO"


def test_runner_multimodal_aprova_smoke_sintetico(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out_dir = tmp_path / "out_ok"
    monkeypatch.setattr(
        sys,
        "argv",
        ["avaliar_multimodal.py", "--synthetic-smoke", "--out-dir", str(out_dir)],
    )
    codigo = avaliar_multimodal.main()
    assert codigo == 0
    relatorio = json.loads((out_dir / "resultado.json").read_text(encoding="utf-8"))
    assert relatorio["aprovados_funcionais"] == 8
    assert relatorio["gates"]["funcional_e_lgpd"] == "APROVADO"
    assert relatorio["gates"]["rnf04_p95_8000ms"] == "APROVADO"
