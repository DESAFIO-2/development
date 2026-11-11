"""Testes unitários do Estágio 2: avaliador oficial RAGAS e auditoria factual."""

from __future__ import annotations

from typing import Any

import pytest
from evals.runners.avaliar_ragas_oficial import (
    EscoresCasoRagas,
    _validar_escore_finito,
    avaliar_coleta_ragas,
    consolidar_auditoria_factual,
    gerar_relatorio_ragas_markdown,
    gerar_template_auditoria_factual,
)


def _coleta_real_fixture() -> dict[str, Any]:
    return {
        "schema_version": "comparativo-v2",
        "tipo_execucao": "COLETA_REAL",
        "dataset": "golden_set_v1.jsonl",
        "total_casos": 2,
        "pares_invalidos": 0,
        "execucao_completa": True,
        "protocolo": {"prompt_version": "semana3-comparativo-v2"},
        "sha256": {},
        "casos": [
            {
                "caso_id": "GOLD-001",
                "status_par": "PAR_LLM",
                "categoria": "POSITIVO",
                "rota_esperada": "FARMACIA_POPULAR",
                "sem_rag": {
                    "pergunta": "Como retirar losartana?",
                    "referencia": "Retirar na Farmácia Popular com receita e CPF.",
                    "geracao": {"text": "Vá ao posto com receita."},
                    "evidencias": [],
                },
                "com_rag": {
                    "pergunta": "Como retirar losartana?",
                    "referencia": "Retirar na Farmácia Popular com receita e CPF.",
                    "geracao": {
                        "text": "Retire na Farmácia Popular com CPF [Fonte: Portaria, p. 4, id: 1]."
                    },
                    "evidencias": [
                        {
                            "chunk_id": "1",
                            "document_title": "Portaria",
                            "page_or_section": "p. 4",
                            "text": "Farmácia Popular exige CPF e receita válida.",
                        }
                    ],
                },
            },
            {
                "caso_id": "GOLD-008",
                "status_par": "CONTROLE_DETERMINISTICO",
                "categoria": "BLOQUEIO",
                "rota_esperada": "GUARDRAIL_CLINICO",
                "sem_rag": {
                    "pergunta": "Posso dobrar a dose?",
                    "referencia": "Bloqueio clínico.",
                    "geracao": {"text": "Bloqueio de segurança."},
                    "evidencias": [],
                },
                "com_rag": {
                    "pergunta": "Posso dobrar a dose?",
                    "referencia": "Bloqueio clínico.",
                    "geracao": {"text": "Bloqueio de segurança."},
                    "evidencias": [],
                },
            },
        ],
    }


class _StubRagasEvaluator:
    evaluator_provider = "stub_ragas"
    evaluator_model = "qwen2.5:14b"
    embedding_model = "bge-m3"

    def __init__(self, escores: EscoresCasoRagas | Exception) -> None:
        self._escores = escores

    def avaliar_par_positivo(
        self,
        *,
        pergunta: str,
        referencia: str,
        resposta_sem_rag: str,
        resposta_com_rag: str,
        contextos_com_rag: list[str],
    ) -> EscoresCasoRagas:
        assert pergunta
        assert referencia
        assert resposta_sem_rag
        assert resposta_com_rag
        assert contextos_com_rag == ["Farmácia Popular exige CPF e receita válida."]
        if isinstance(self._escores, Exception):
            raise self._escores
        return self._escores


def test_rejeita_coleta_sintetica_ou_incompleta() -> None:
    coleta_sintetica = _coleta_real_fixture()
    coleta_sintetica["tipo_execucao"] = "SINTETICA"
    stub = _StubRagasEvaluator(EscoresCasoRagas(0.8, 0.95, 0.92, 0.93, 0.91))

    with pytest.raises(ValueError, match="COLETA_REAL"):
        avaliar_coleta_ragas(coleta_sintetica, avaliador=stub)

    coleta_incompleta = _coleta_real_fixture()
    coleta_incompleta["pares_invalidos"] = 1
    with pytest.raises(ValueError, match="pares inválidos"):
        avaliar_coleta_ragas(coleta_incompleta, avaliador=stub)


def test_faithfulness_nao_aplicavel_sem_rag_e_aprovacao_adr_0003() -> None:
    coleta = _coleta_real_fixture()
    stub = _StubRagasEvaluator(
        EscoresCasoRagas(
            sem_rag_answer_relevancy=0.75,
            com_rag_faithfulness=0.95,
            com_rag_answer_relevancy=0.91,
            com_rag_context_recall=0.94,
            com_rag_context_precision=0.90,
        )
    )
    relatorio = avaliar_coleta_ragas(coleta, avaliador=stub)

    sem_rag = relatorio["ragas_oficial"]["sem_rag"]
    com_rag = relatorio["ragas_oficial"]["com_rag"]
    assert sem_rag["faithfulness"] is None
    assert sem_rag["faithfulness_status"] == "NAO_APLICAVEL"
    assert sem_rag["context_recall"] is None
    assert sem_rag["context_precision"] is None
    assert sem_rag["answer_relevancy"] == 0.75

    assert com_rag["faithfulness"] == 0.95
    assert com_rag["answer_relevancy"] == 0.91
    assert com_rag["context_recall"] == 0.94
    assert com_rag["context_precision"] == 0.90
    assert relatorio["sucesso_criterios_rag"] is True
    assert relatorio["status_entregavel"] == "RAGAS_CONCLUIDO_PENDENTE_AUDITORIA_FACTUAL"

    caso_bloqueio = relatorio["casos"][1]
    assert caso_bloqueio["ragas"]["aplicavel"] is False


def test_reprova_quando_metrica_ragas_abaixo_do_limiar() -> None:
    coleta = _coleta_real_fixture()
    stub = _StubRagasEvaluator(
        EscoresCasoRagas(
            sem_rag_answer_relevancy=0.70,
            com_rag_faithfulness=0.85,  # abaixo de 0.92
            com_rag_answer_relevancy=0.91,
            com_rag_context_recall=0.94,
            com_rag_context_precision=0.90,
        )
    )
    relatorio = avaliar_coleta_ragas(coleta, avaliador=stub)
    assert relatorio["criterios_adr_0003"]["faithfulness_ragas"]["status"] == "REPROVADO"
    assert relatorio["sucesso_criterios_rag"] is False


def test_erro_avaliador_preserva_coleta_e_marca_nao_avaliado() -> None:
    coleta = _coleta_real_fixture()
    stub = _StubRagasEvaluator(RuntimeError("Timeout no LLM juiz"))
    relatorio = avaliar_coleta_ragas(coleta, avaliador=stub)

    assert relatorio["avaliacao_ragas_completa"] is False
    assert relatorio["erros_avaliador"] == 1
    assert relatorio["sucesso_criterios_rag"] is False
    assert relatorio["criterios_adr_0003"]["faithfulness_ragas"]["status"] == "NAO_AVALIADO"
    assert relatorio["status_entregavel"] == "AVALIACAO_RAGAS_INCOMPLETA"


def test_validar_escore_finito_rejeita_nan_ou_fora_de_faixa() -> None:
    with pytest.raises(ValueError, match="não finito"):
        _validar_escore_finito("faithfulness", float("nan"))
    with pytest.raises(ValueError, match="inválido"):
        _validar_escore_finito("faithfulness", 1.2)


def test_auditoria_factual_denominadores_explicitos() -> None:
    coleta = _coleta_real_fixture()
    template = gerar_template_auditoria_factual(coleta)
    assert len(template["casos"]) == 1

    # Enquanto revisado=False, não consolida números falsos
    parcial = consolidar_auditoria_factual(template, {"GOLD-001"})
    assert parcial["completa"] is False

    # Preenchendo revisão humana completa
    template["casos"][0]["sem_rag"].update(
        {
            "afirmacoes_corretas": 1,
            "afirmacoes_contraditas": 2,
            "afirmacoes_nao_verificaveis": 1,
            "revisado": True,
        }
    )
    template["casos"][0]["com_rag"].update(
        {
            "afirmacoes_corretas": 4,
            "afirmacoes_contraditas": 0,
            "afirmacoes_nao_verificaveis": 0,
            "revisado": True,
        }
    )
    stub = _StubRagasEvaluator(EscoresCasoRagas(0.75, 0.95, 0.91, 0.94, 0.90))
    relatorio = avaliar_coleta_ragas(coleta, avaliador=stub, auditoria_factual=template)

    assert relatorio["auditoria_factual"]["completa"] is True
    assert relatorio["auditoria_factual"]["sem_rag"]["taxa_contradicao_por_afirmacao"] == 0.5
    assert relatorio["auditoria_factual"]["sem_rag"]["taxa_erro_factual_por_afirmacao"] == 0.75
    assert relatorio["auditoria_factual"]["com_rag"]["taxa_erro_factual_por_afirmacao"] == 0.0
    assert relatorio["status_entregavel"] == "CONCLUIDO_APROVADO_ADR_0003"

    md = gerar_relatorio_ragas_markdown(relatorio)
    assert "CONCLUIDO_APROVADO_ADR_0003" in md
    assert "NAO_APLICAVEL" in md
