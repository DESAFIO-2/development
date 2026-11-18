"""Camada de saída: o texto da LLM só chega ao cidadão se passar daqui.

Complementa a esteira de entrada (OWASP LLM01) com três regras determinísticas:

- PII na resposta (OWASP LLM02 Sensitive Information Disclosure): CPF, Cartão SUS,
  RG, CRM, CID-10, CEP, endereço, telefone, e-mail ou nome de paciente, com os
  mesmos padrões do `PIIMasker`.
- Orientação de dose, fracionamento, compartilhamento ou troca de remédio
  (OWASP LLM05 Improper Output Handling): ato médico (Lei nº 12.842/2013).
  Frases negadas na mesma cláusula ("não troque o remédio") passam como aviso.
- Citação de documento fora do contexto (OWASP LLM09 Misinformation): toda citação
  `Fonte: ID | título` precisa apontar um chunk que a busca realmente devolveu.

O log registra só a decisão e os motivos, nunca o texto (LGPD).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass

from app.guardrails.pii import PIIMasker
from app.seguranca.citacoes import ids_citados
from app.seguranca.texto import limpar

logger = logging.getLogger("app.seguranca")

_ACAO = (
    r"\b(?:dobr|aument|diminu|reduz|suspend|interromp|substitu|troc|troqu"
    r"|part|quebr|divid|cort|compartilh|emprest)\w*"
)
_ALVO = (
    r"(?:a dose|as doses|a dosagem|o remedio|os remedios|o medicamento|os medicamentos"
    r"|a medicacao|o comprimido|os comprimidos|a capsula|as capsulas|o xarope)"
)
_QUANTIDADE = r"(?:\d+(?:[.,]\d+)?|um|uma|dois|duas|tres|quatro|cinco|seis|meio|meia)"
_POSOLOGIA = re.compile(
    rf"{_ACAO}(?:\W+\w+){{0,3}}?\W+{_ALVO}"
    rf"|\bde {_QUANTIDADE} em {_QUANTIDADE} ?h(?:oras)?\b"
    rf"|\ba cada {_QUANTIDADE} ?h(?:oras)?\b"
    rf"|\b{_QUANTIDADE} ?(?:x|vezes) (?:ao|por) dia\b"
    rf"|\b(?:tom[ea]r?|us[ea]r?|aplic[ae]r?|inger[iu]\w*) "
    rf"{_QUANTIDADE} (?:comprimidos?|capsulas?|gotas|doses?|ampolas?)\b"
)
# Delimitador de oração (inclui vírgula) impede que negação inicial libere cláusula seguinte.
_FRONTEIRA_CLAUSULA = re.compile(r"(?:[.,;!?]|\b(?:mas|porem|contudo|entretanto|todavia)\b)")
_NEGACAO = re.compile(r"\b(?:nao|nunca|jamais|evite|sem orientacao|sem falar)\b[^.,;!?]{0,40}$")
# Cada documento citado: "Fonte: <ID> | <título>". "[Fonte: Conhecimento Geral]" não
# afirma documento nenhum e por isso não é tratado como citação.
_CITACAO_DOCUMENTO = re.compile(r"fonte\s*:\s*([^|\]\n;]+?)\s*\|", re.IGNORECASE)

_PII = PIIMasker()


@dataclass(frozen=True)
class ResultadoSaida:
    aprovada: bool
    motivos: tuple[str, ...]


def forma_para_regras(texto: str) -> str:
    """Minúscula e sem acento, mas mantendo dígitos (o "8" de "8 em 8 horas")."""
    base = limpar(texto).lower()
    return unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()


def negado_na_clausula(forma: str, inicio: int) -> bool:
    """Há negação na mesma oração, antes de `inicio`? `forma` já normalizada."""
    prefixo = forma[:inicio]
    ultimo_corte = 0
    for fronteira in _FRONTEIRA_CLAUSULA.finditer(prefixo):
        ultimo_corte = fronteira.end()
    return bool(_NEGACAO.search(prefixo[ultimo_corte:]))


def orienta_posologia(texto: str) -> bool:
    """O texto orienta dose, fracionamento, compartilhamento ou troca (fora de negação)?"""
    forma = forma_para_regras(texto)
    return any(
        not negado_na_clausula(forma, achado.start()) for achado in _POSOLOGIA.finditer(forma)
    )


def citacoes_fora_do_contexto(texto: str, ids_contexto: Collection[str]) -> list[str]:
    """IDs citados que não vieram da busca.

    Confere o formato completo (`Fonte: ID | título`) e o curto do protocolo v3
    (`[CHK-ID]`): um ID curto que escapasse da expansão também é citação.
    """
    permitidos = set(ids_contexto)
    normalizado = limpar(texto)
    citados = [m.group(1).strip() for m in _CITACAO_DOCUMENTO.finditer(normalizado)]
    citados.extend(ids_citados(normalizado))
    return [chunk_id for chunk_id in citados if chunk_id not in permitidos]


def validar_saida(texto: str, ids_contexto: Collection[str] = ()) -> ResultadoSaida:
    """Decide se a resposta gerada pode ser mostrada ao cidadão."""
    motivos = [f"PII_{tipo}" for tipo in _PII.mascarar(texto).tipos_detectados]
    if orienta_posologia(texto):
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
