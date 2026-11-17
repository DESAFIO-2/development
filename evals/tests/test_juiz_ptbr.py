"""Item 4: prompts do juiz em pt-BR no ragas==0.4.3 instalado. NÃO mede qualidade de LLM."""

from __future__ import annotations

from evals.metrics.prompts_ptbr import (
    INSTRUCAO_AFIRMACOES,
    INSTRUCAO_NLI,
    INSTRUCAO_RELEVANCIA,
    sha256_prompts_ptbr,
)
from evals.runners.avaliar_ragas_oficial import OfficialRagasCollectionsEvaluator
from ragas.metrics.collections.answer_relevancy.util import (
    AnswerRelevanceInput,
    AnswerRelevancePrompt,
)
from ragas.metrics.collections.faithfulness.util import NLIStatementInput


def _avaliador(ptbr: bool) -> OfficialRagasCollectionsEvaluator:
    return OfficialRagasCollectionsEvaluator(
        evaluator_model="fixture", embedding_model="fixture-embedding", prompts_ptbr=ptbr
    )


def test_prompts_ptbr_trocam_instrucao_e_exemplos_sem_mudar_os_modelos() -> None:
    avaliador = _avaliador(True)
    try:
        relevancia = avaliador._answer_relevancy.prompt
        texto = relevancia.to_string(AnswerRelevanceInput(response="Leve o CPF."))
        assert texto.startswith(INSTRUCAO_RELEVANCIA)
        assert "losartana" in texto
        assert "Einstein" not in texto
        assert relevancia.output_model.__name__ == "AnswerRelevanceOutput"
        faithfulness = avaliador._faithfulness
        assert faithfulness.statement_generator_prompt.instruction == INSTRUCAO_AFIRMACOES
        nli = faithfulness.nli_statement_prompt.to_string(
            NLIStatementInput(context="c", statements=["a"])
        )
        assert nli.startswith(INSTRUCAO_NLI)
        assert "John" not in nli
    finally:
        avaliador.close()


def test_original_continua_em_ingles_e_a_classe_do_ragas_nao_muda() -> None:
    original = _avaliador(False)
    traduzido = _avaliador(True)
    try:
        assert original._answer_relevancy.prompt.instruction.startswith("Generate a question")
        assert AnswerRelevancePrompt.instruction.startswith("Generate a question")
        assert traduzido._answer_relevancy.prompt.instruction == INSTRUCAO_RELEVANCIA
    finally:
        original.close()
        traduzido.close()


def test_hash_dos_prompts_e_estavel() -> None:
    assert sha256_prompts_ptbr() == sha256_prompts_ptbr()
    assert len(sha256_prompts_ptbr()) == 64
