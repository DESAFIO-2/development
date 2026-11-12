"""Variante blindada do braço com RAG (braço D do comparativo de quatro braços).

Envolve qualquer GeneratorPort sem mudar prompt, modelo, temperatura ou busca do
protocolo `semana3-v2`. A diferença entre o braço B (LLM com RAG) e o braço D é
só a defesa acrescentada:

1. Entrada: esteira anti-injection (`app.seguranca.inspecionar_entrada`, OWASP LLM01),
   que barra a pergunta antes de chamar o modelo. O guardrail clínico e o
   mascaramento de PII da entrada já existem no gerador e valem para B e D.
2. Saída: `app.seguranca.saida.validar_saida` (PII, posologia/troca e citação fora
   do contexto; OWASP LLM02, LLM05 e LLM09).

Saída reprovada: o texto vira uma mensagem segura, mas o par continua
`execution_kind="llm"`, porque o modelo foi chamado; o RAGAS mede o que o cidadão
veria. O motivo e o SHA-256 do texto original ficam em `provider_metadata`.
Entrada barrada: o modelo não é chamado e o resultado é um controle (`guardrail`).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import replace
from typing import Any

from app.application.ports import GenerationResultDTO, GeneratorPort, RetrievalHitDTO
from app.seguranca import Canal, inspecionar_entrada
from app.seguranca.saida import validar_saida

MSG_BLOQUEIO_ENTRADA = (
    "Não posso processar esta mensagem porque ela contém instruções que não fazem "
    "parte de uma pergunta sobre acesso ao SUS. Reformule a sua dúvida, por favor."
)
MSG_BLOQUEIO_SAIDA = (
    "Não posso mostrar esta resposta com segurança. Para dúvidas sobre dose, troca "
    "ou uso de remédios, procure a equipe da sua UBS ou o seu médico."
)
# Resultados que não são texto gerado: nada a validar na saída.
_SEM_TEXTO_GERADO = {"guardrail", "abstention"}


class GeradorBlindado(GeneratorPort):
    def __init__(self, interno: GeneratorPort) -> None:
        self.interno = interno

    def __getattr__(self, nome: str) -> Any:
        # provider, model_name, base_url e timeout_seconds vêm do gerador interno,
        # para o manifesto da coleta registrar o modelo real.
        return getattr(self.interno, nome)

    def generate(
        self,
        question: str,
        evidences: tuple[RetrievalHitDTO, ...] = (),
        *,
        rag_mode: bool | None = None,
    ) -> GenerationResultDTO:
        inicio = time.perf_counter()
        entrada = inspecionar_entrada(question, Canal.TEXTO)
        if entrada.bloqueado:
            return GenerationResultDTO(
                text=MSG_BLOQUEIO_ENTRADA,
                provider=str(getattr(self.interno, "provider", "synthetic")),
                model_name=str(getattr(self.interno, "model_name", "synthetic")),
                grounded=bool(evidences) if rag_mode is None else rag_mode,
                latency_ms=round((time.perf_counter() - inicio) * 1000, 2),
                execution_kind="guardrail",
                provider_metadata={
                    "seguranca_camada": "entrada",
                    "seguranca_motivos": list(entrada.motivos),
                },
            )
        resultado = self.interno.generate(question, evidences, rag_mode=rag_mode)
        if resultado.error_code or resultado.execution_kind in _SEM_TEXTO_GERADO:
            return resultado
        saida = validar_saida(resultado.text, [hit.chunk_id for hit in evidences])
        if saida.aprovada:
            return resultado
        return replace(
            resultado,
            text=MSG_BLOQUEIO_SAIDA,
            provider_metadata={
                **(resultado.provider_metadata or {}),
                "seguranca_camada": "saida",
                "seguranca_motivos": list(saida.motivos),
                "texto_original_sha256": hashlib.sha256(resultado.text.encode("utf-8")).hexdigest(),
            },
        )
