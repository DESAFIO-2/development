"""Item 1: segunda camada (Llama Guard 3) pronta para medir, com falha nunca virando acerto."""

from __future__ import annotations

import io
import json
import logging
import urllib.error
from typing import Any
from unittest.mock import patch

import pytest

from app.guardrails import segunda_camada
from app.guardrails.segunda_camada import (
    ClassificadorLlamaGuard,
    SegundaCamadaIndisponivel,
    interpretar_saida,
)


def _resposta(conteudo: str) -> io.BytesIO:
    corpo = io.BytesIO(json.dumps({"message": {"content": conteudo}}).encode())
    corpo.__enter__ = lambda: corpo  # type: ignore[method-assign]
    corpo.__exit__ = lambda *a: None  # type: ignore[method-assign]
    return corpo


@pytest.mark.parametrize(
    ("saida", "esperado"),
    [
        ("safe", (False, ())),
        ("unsafe\nS6", (True, ("S6",))),
        ("  unsafe \n S6,S2 ", (True, ("S6", "S2"))),
        ("unsafe", (True, ())),
    ],
)
def test_interpreta_safe_e_unsafe_com_categorias(
    saida: str, esperado: tuple[bool, tuple[str, ...]]
) -> None:
    assert interpretar_saida(saida) == esperado


@pytest.mark.parametrize("saida", ["", "talvez", "Claro! Posso ajudar."])
def test_saida_fora_do_formato_e_erro(saida: str) -> None:
    with pytest.raises(ValueError):
        interpretar_saida(saida)


def test_chama_api_chat_com_temperatura_zero_seed_e_pii_mascarado() -> None:
    pedidos: list[dict[str, Any]] = []

    def urlopen(pedido: Any, timeout: float) -> io.BytesIO:
        assert pedido.full_url == "http://ollama:11434/api/chat"
        pedidos.append(json.loads(pedido.data))
        return _resposta("unsafe\nS6")

    classificador = ClassificadorLlamaGuard(base_url="http://ollama:11434/")
    with patch("urllib.request.urlopen", urlopen):
        decisao = classificador.classificar("Meu CPF é 123.456.789-00, posso dobrar a dose?")
    assert decisao.bloqueado and decisao.categorias == ("S6",)
    corpo = pedidos[0]
    assert corpo["model"] == "llama-guard3:1b"
    assert corpo["options"] == {"temperature": 0.0, "seed": 42}
    assert "123.456" not in corpo["messages"][0]["content"]


def test_com_resposta_julga_a_ultima_mensagem_do_assistente() -> None:
    mensagens: list[list[dict[str, str]]] = []

    def urlopen(pedido: Any, timeout: float) -> io.BytesIO:
        mensagens.append(json.loads(pedido.data)["messages"])
        return _resposta("safe")

    with patch("urllib.request.urlopen", urlopen):
        ClassificadorLlamaGuard().classificar("onde pego?", "Na UBS.")
    assert [m["role"] for m in mensagens[0]] == ["user", "assistant"]


def _fora_do_ar(pedido: Any, timeout: float) -> io.BytesIO:
    raise urllib.error.URLError("connection refused")


def test_producao_falha_fechada() -> None:
    with patch("urllib.request.urlopen", _fora_do_ar):
        decisao = ClassificadorLlamaGuard(modo="producao").classificar("onde pego?")
    assert decisao.bloqueado and decisao.falha_fechada


def test_avaliacao_para_com_erro_para_falha_nunca_virar_acerto() -> None:
    with (
        patch("urllib.request.urlopen", _fora_do_ar),
        pytest.raises(SegundaCamadaIndisponivel),
    ):
        ClassificadorLlamaGuard(modo="avaliacao").classificar("onde pego?")


def test_log_leva_so_decisao_categorias_e_latencia(caplog: pytest.LogCaptureFixture) -> None:
    with (
        patch("urllib.request.urlopen", lambda p, timeout: _resposta("unsafe\nS6")),
        caplog.at_level(logging.INFO, logger="app.guardrails"),
    ):
        ClassificadorLlamaGuard().classificar("posso dobrar a dose da losartana?")
    registro = next(r for r in caplog.records if r.getMessage() == "decisao_segunda_camada")
    assert registro.__dict__["segunda_camada_categorias"] == ["S6"]
    assert "losartana" not in json.dumps(registro.__dict__, default=str)


def test_alvos_do_runner_camada_2_e_combinado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(segunda_camada, "_AVALIACAO", None)
    with patch("urllib.request.urlopen", lambda p, timeout: _resposta("safe")):
        assert segunda_camada.deve_bloquear("onde pego losartana?") is False
        # Camada 1 bloqueia sozinha: o combinado bloqueia mesmo com a camada 2 "safe".
        assert segunda_camada.deve_bloquear_combinado("Posso dobrar a dose da Losartana?")
