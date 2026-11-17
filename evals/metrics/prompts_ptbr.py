"""Prompts do juiz RAGAS em português, do domínio SUS-DF (avaliação `ragas_v2`).

Motivo (coleta de 12/11): o juiz gerava as perguntas do Answer Relevancy em inglês
("How can I obtain...") e o `bge-m3` comparava com a consulta em português.

O que muda e o que não muda, conferido no código instalado do `ragas==0.4.3`:
- Muda só `instruction` e `examples` dos prompts `prompt` (AnswerRelevancy),
  `statement_generator_prompt` e `nli_statement_prompt` (Faithfulness).
- Os modelos pydantic de entrada e saída são os mesmos, então a conta não muda.
- Não usamos `adapt()` do ragas: ele traduz com a própria LLM e o texto mudaria a
  cada rodada. Aqui o texto é fixo e o SHA-256 entra no manifesto da avaliação.
- O molde em volta ("Please return the output in a JSON format...") continua em
  inglês, porque está fixo em `BasePrompt.to_string`.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ragas.metrics.collections.answer_relevancy.util import (
    AnswerRelevanceInput,
    AnswerRelevanceOutput,
)
from ragas.metrics.collections.faithfulness.util import (
    NLIStatementInput,
    NLIStatementOutput,
    StatementFaithfulnessAnswer,
    StatementGeneratorInput,
    StatementGeneratorOutput,
)

INSTRUCAO_RELEVANCIA = (
    "Escreva, em português do Brasil, uma pergunta que a resposta dada responde e "
    "diga se a resposta é evasiva. Use noncommittal = 1 se a resposta for evasiva, "
    "vaga ou ambígua e 0 se for substantiva. Exemplos de respostas evasivas: "
    '"Não sei", "Não tenho certeza", "Depende".'
)
EXEMPLOS_RELEVANCIA = [
    (
        AnswerRelevanceInput(
            response=(
                "A losartana 50 mg é gratuita no Programa Farmácia Popular. "
                "Leve receita válida, documento oficial com foto e CPF."
            )
        ),
        AnswerRelevanceOutput(
            question="Onde consigo losartana 50 mg de graça e o que preciso levar?",
            noncommittal=0,
        ),
    ),
    (
        AnswerRelevanceInput(
            response=(
                "Para consulta com especialista, peça o encaminhamento na sua UBS; "
                "a marcação é feita pela regulação no SISREG."
            )
        ),
        AnswerRelevanceOutput(
            question="Como marco consulta com especialista pelo SUS no DF?",
            noncommittal=0,
        ),
    ),
    (
        AnswerRelevanceInput(response="Não sei informar se esse remédio está disponível agora."),
        AnswerRelevanceOutput(
            question="Esse remédio está disponível agora na UBS?",
            noncommittal=1,
        ),
    ),
]

INSTRUCAO_AFIRMACOES = (
    "Dada uma pergunta e uma resposta, analise cada frase da resposta e divida-a em "
    "uma ou mais afirmações compreensíveis sozinhas, em português do Brasil. "
    "Não use pronomes nas afirmações: repita o nome do que está sendo afirmado."
)
EXEMPLOS_AFIRMACOES = [
    (
        StatementGeneratorInput(
            question="Onde retiro a insulina NPH no DF?",
            answer=(
                "Ela é distribuída nas UBS do DF. Para retirar, a pessoa apresenta a "
                "receita e o cartão do SUS."
            ),
        ),
        StatementGeneratorOutput(
            statements=[
                "A insulina NPH é distribuída nas UBS do DF.",
                "Para retirar a insulina NPH, é preciso apresentar a receita.",
                "Para retirar a insulina NPH, é preciso apresentar o cartão do SUS.",
            ]
        ),
    ),
]

INSTRUCAO_NLI = (
    "Sua tarefa é julgar a fidelidade de uma lista de afirmações a um contexto. Para "
    "cada afirmação, responda verdict = 1 se ela pode ser inferida diretamente do "
    "contexto e verdict = 0 se não pode. Escreva o motivo em português do Brasil."
)
EXEMPLOS_NLI = [
    (
        NLIStatementInput(
            context=(
                "O Programa Farmácia Popular do Brasil oferece gratuitamente medicamentos "
                "para hipertensão, diabetes e asma em farmácias credenciadas. Para retirar, "
                "o paciente apresenta documento oficial com foto, CPF e receita válida."
            ),
            statements=[
                "A losartana é gratuita na Farmácia Popular.",
                "É preciso apresentar o CPF para retirar medicamentos na Farmácia Popular.",
                "A receita da Farmácia Popular vale por 365 dias.",
                "A retirada é feita em farmácias credenciadas.",
            ],
        ),
        NLIStatementOutput(
            statements=[
                StatementFaithfulnessAnswer(
                    statement="A losartana é gratuita na Farmácia Popular.",
                    reason=(
                        "O contexto fala de medicamentos para hipertensão, mas não cita "
                        "a losartana."
                    ),
                    verdict=0,
                ),
                StatementFaithfulnessAnswer(
                    statement=(
                        "É preciso apresentar o CPF para retirar medicamentos na Farmácia Popular."
                    ),
                    reason="O contexto lista o CPF entre os documentos exigidos.",
                    verdict=1,
                ),
                StatementFaithfulnessAnswer(
                    statement="A receita da Farmácia Popular vale por 365 dias.",
                    reason="O contexto não informa a validade da receita.",
                    verdict=0,
                ),
                StatementFaithfulnessAnswer(
                    statement="A retirada é feita em farmácias credenciadas.",
                    reason="O contexto diz que o programa funciona em farmácias credenciadas.",
                    verdict=1,
                ),
            ]
        ),
    ),
]


def _conteudo() -> dict[str, Any]:
    return {
        "relevancia": [
            INSTRUCAO_RELEVANCIA,
            [(e.model_dump(), s.model_dump()) for e, s in EXEMPLOS_RELEVANCIA],
        ],
        "afirmacoes": [
            INSTRUCAO_AFIRMACOES,
            [(e.model_dump(), s.model_dump()) for e, s in EXEMPLOS_AFIRMACOES],
        ],
        "nli": [INSTRUCAO_NLI, [(e.model_dump(), s.model_dump()) for e, s in EXEMPLOS_NLI]],
    }


def sha256_prompts_ptbr() -> str:
    """Identidade do texto exato dos prompts, para o manifesto da avaliação."""
    texto = json.dumps(_conteudo(), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def aplicar_prompts_ptbr(faithfulness: Any, answer_relevancy: Any) -> None:
    """Troca instrução e exemplos nas instâncias das métricas (não na classe do ragas)."""
    answer_relevancy.prompt.instruction = INSTRUCAO_RELEVANCIA
    answer_relevancy.prompt.examples = list(EXEMPLOS_RELEVANCIA)
    faithfulness.statement_generator_prompt.instruction = INSTRUCAO_AFIRMACOES
    faithfulness.statement_generator_prompt.examples = list(EXEMPLOS_AFIRMACOES)
    faithfulness.nli_statement_prompt.instruction = INSTRUCAO_NLI
    faithfulness.nli_statement_prompt.examples = list(EXEMPLOS_NLI)
