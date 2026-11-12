"""Camada de saída da LLM: PII, posologia/troca e citação fora do contexto."""

from __future__ import annotations

import logging

import pytest

from app.seguranca.saida import citacoes_fora_do_contexto, validar_saida

FONTE_OK = "[Fonte: CHK-PFPB-001 | Portaria GM/MS nº 3.677/2024, p. 11]"


def test_resposta_administrativa_com_citacao_recuperada_passa() -> None:
    texto = f"A losartana é gratuita na Farmácia Popular com receita e CPF. {FONTE_OK}"
    assert validar_saida(texto, ["CHK-PFPB-001"]).aprovada


@pytest.mark.parametrize(
    ("texto", "motivo"),
    [
        ("Seu CPF 123.456.789-00 está cadastrado.", "PII_CPF"),
        ("Cartão SUS 898 0000 0000 0000 confirmado.", "PII_CNS_CARTAO_SUS"),
        ("Envie para fulano.teste@example.com", "PII_EMAIL"),
        ("Ligue para (61) 99999-0000.", "PII_PHONE"),
    ],
)
def test_pii_na_resposta_reprova(texto: str, motivo: str) -> None:
    resultado = validar_saida(texto)
    assert not resultado.aprovada
    assert motivo in resultado.motivos


@pytest.mark.parametrize(
    "texto",
    [
        "Você pode dobrar a dose amanhã.",
        "Pode trocar o remédio pelo genérico de outra marca.",
        "Tome de 8 em 8 horas.",
        "Use a cada 12h até melhorar.",
        "Tome 2 comprimidos antes de dormir.",
        "O ideal é 3 vezes ao dia.",
    ],
)
def test_orientacao_de_posologia_ou_troca_reprova(texto: str) -> None:
    resultado = validar_saida(texto)
    assert resultado.motivos == ("ORIENTACAO_POSOLOGIA_OU_TROCA",)


@pytest.mark.parametrize(
    "texto",
    [
        "Não troque o remédio sem orientação do seu médico.",
        "Nunca aumente a dose por conta própria.",
        "Evite suspender o medicamento sem falar com a equipe da UBS.",
        "A receita vale por 180 dias para uso contínuo.",
    ],
)
def test_aviso_de_seguranca_negado_passa(texto: str) -> None:
    assert validar_saida(texto).aprovada


def test_citacao_de_chunk_nao_recuperado_reprova() -> None:
    resultado = validar_saida(FONTE_OK, ["CHK-OUTRO-001"])
    assert resultado.motivos == ("CITACAO_FORA_DO_CONTEXTO",)


def test_molde_do_prompt_sem_evidencia_reprova() -> None:
    # Caso real do GOLD-022 sem RAG na coleta de 12/11.
    texto = "Leve o LME. [Fonte: ID_DO_CHUNK | Declaração Autorizadora do LME]"
    assert citacoes_fora_do_contexto(texto, []) == ["ID_DO_CHUNK"]


def test_duas_fontes_no_mesmo_colchete_sao_conferidas() -> None:
    texto = "[Fonte: CHK-A | Título A, p. 1; Fonte: CHK-B | Título B, p. 2]"
    assert citacoes_fora_do_contexto(texto, ["CHK-A"]) == ["CHK-B"]
    assert citacoes_fora_do_contexto(texto, ["CHK-A", "CHK-B"]) == []


def test_fonte_sem_documento_nao_e_citacao() -> None:
    # "[Fonte: Conhecimento Geral]" (GOLD-008 sem RAG) não afirma documento nenhum.
    assert validar_saida("Procure a UBS. [Fonte: Conhecimento Geral]").aprovada


def test_log_nao_registra_o_texto(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.seguranca"):
        validar_saida("Seu CPF 123.456.789-00 está cadastrado.")
    registro = caplog.records[-1]
    assert "123.456" not in registro.getMessage()
    assert registro.__dict__["seguranca_saida_motivos"] == ["PII_CPF"]
