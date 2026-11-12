"""Camada de saída: o texto da LLM só chega ao cidadão se passar daqui.

Complementa a esteira de entrada (OWASP LLM01) com três regras determinísticas:

- PII na resposta (OWASP LLM02 Sensitive Information Disclosure): CPF, Cartão SUS,
  telefone, e-mail ou nome de paciente, com os mesmos padrões do `PIIMasker`.
- Orientação de dose ou de troca de remédio (OWASP LLM05 Improper Output Handling):
  isso é ato médico (Lei nº 12.842/2013). Frases negadas ("não troque o remédio")
  são avisos de segurança e passam.
- Citação de documento fora do contexto (OWASP LLM09 Misinformation): toda citação
  `Fonte: ID | título` precisa apontar um chunk que a busca realmente devolveu.
  Esta regra NÃO confere título e página (isso é a validação estrita do comparativo)
  e citação válida não prova veracidade factual (diretrizes, Regra 3).

O log registra só a decisão e os motivos, nunca o texto (LGPD).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass

from app.guardrails.pii import PIIMasker
from app.seguranca.texto import limpar

logger = logging.getLogger("app.seguranca")

_ACAO = r"\b(?:dobr|aument|diminu|reduz|suspend|interromp|substitu|troc|troqu)\w*"
_ALVO = (
    r"(?:a dose|as doses|a dosagem|o remedio|os remedios|o medicamento|os medicamentos"
    r"|a medicacao|o comprimido|os comprimidos)"
)
_POSOLOGIA = re.compile(
    rf"{_ACAO}(?:\W+\w+){{0,2}}?\W+{_ALVO}"
    r"|\bde \d+ em \d+ ?h(?:oras)?\b"
    r"|\ba cada \d+ ?h(?:oras)?\b"
    r"|\b\d+ ?(?:x|vezes) (?:ao|por) dia\b"
    r"|\btom[ea]r? \d+ (?:comprimidos?|capsulas?|gotas|doses?)\b"
)
# "não", "nunca", "sem orientação" etc. logo antes transformam a frase em aviso.
_NEGACAO = re.compile(r"\b(?:nao|nunca|jamais|evite|sem orientacao|sem falar)\b[^.;!?]{0,40}$")
# Cada documento citado: "Fonte: <ID> | <título>". "[Fonte: Conhecimento Geral]" não
# afirma documento nenhum e por isso não é tratado como citação.
_CITACAO_DOCUMENTO = re.compile(r"fonte\s*:\s*([^|\]\n;]+?)\s*\|", re.IGNORECASE)

_PII = PIIMasker()


@dataclass(frozen=True)
class ResultadoSaida:
    aprovada: bool
    motivos: tuple[str, ...]


def _forma_para_regras(texto: str) -> str:
    """Minúscula e sem acento, mas mantendo dígitos (o "8" de "8 em 8 horas")."""
    base = limpar(texto).lower()
    return unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()


def _orienta_posologia(texto: str) -> bool:
    forma = _forma_para_regras(texto)
    return any(
        not _NEGACAO.search(forma[: achado.start()]) for achado in _POSOLOGIA.finditer(forma)
    )


def citacoes_fora_do_contexto(texto: str, ids_contexto: Collection[str]) -> list[str]:
    """IDs citados como documento que não vieram da busca."""
    permitidos = set(ids_contexto)
    citados = (m.group(1).strip() for m in _CITACAO_DOCUMENTO.finditer(limpar(texto)))
    return [chunk_id for chunk_id in citados if chunk_id not in permitidos]


def validar_saida(texto: str, ids_contexto: Collection[str] = ()) -> ResultadoSaida:
    """Decide se a resposta gerada pode ser mostrada ao cidadão."""
    motivos = [f"PII_{tipo}" for tipo in _PII.mascarar(texto).tipos_detectados]
    if _orienta_posologia(texto):
        motivos.append("ORIENTACAO_POSOLOGIA_OU_TROCA")
    if citacoes_fora_do_contexto(texto, ids_contexto):
        motivos.append("CITACAO_FORA_DO_CONTEXTO")
    resultado = ResultadoSaida(aprovada=not motivos, motivos=tuple(motivos))
    logger.info(
        "decisao_saida_llm",
        extra={
            "seguranca_saida_aprovada": resultado.aprovada,
            "seguranca_saida_motivos": list(resultado.motivos),
        },
    )
    return resultado
