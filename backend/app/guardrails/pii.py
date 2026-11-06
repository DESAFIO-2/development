"""Mascaramento de Dados Pessoais Sensíveis de Saúde (LGPD Art. 11).

Sanitiza CPF, Cartão Nacional de Saúde (CNS), telefone, e-mail e identificação
do paciente antes de qualquer etapa de recuperação ou processamento por IA generativa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PIIMaskingResult:
    """Resultado auditável da desidentificação LGPD."""

    texto_sanitizado: str
    tipos_detectados: list[str]
    total_substituicoes: int


class PIIMasker:
    """Aplica desidentificação determinística preservando fármacos e localidades."""

    _CPF_PATTERN = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
    _CNS_PATTERN = re.compile(r"\b[12789]\d{2}[\s.]?\d{4}[\s.]?\d{4}[\s.]?\d{4}\b")
    _PHONE_PATTERN = re.compile(r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\d{4}|\d{4})[-\s]?\d{4}\b")
    _EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    _PATIENT_NAME_PATTERN = re.compile(
        r"(?i)\b(paciente|nome\s+do\s+paciente|titular)\s*:\s*([A-ZÀ-Úa-zà-ú]+(?:\s+[A-ZÀ-Úa-zà-ú]+){1,4})"
    )

    def mascarar(self, texto: str) -> PIIMaskingResult:
        """Sanitiza PII no texto informado."""
        sanitizado = texto
        tipos_detectados: list[str] = []
        total = 0

        if self._PATIENT_NAME_PATTERN.search(sanitizado):
            sanitizado, count = self._PATIENT_NAME_PATTERN.subn(
                r"\1: [PACIENTE_DESIDENTIFICADO_LGPD]", sanitizado
            )
            total += count
            tipos_detectados.append("PATIENT_NAME")

        if self._CNS_PATTERN.search(sanitizado):
            sanitizado, count = self._CNS_PATTERN.subn("[CNS_MASCARADO_LGPD]", sanitizado)
            total += count
            tipos_detectados.append("CNS_CARTAO_SUS")

        if self._CPF_PATTERN.search(sanitizado):
            sanitizado, count = self._CPF_PATTERN.subn("[CPF_MASCARADO_LGPD]", sanitizado)
            total += count
            tipos_detectados.append("CPF")

        if self._EMAIL_PATTERN.search(sanitizado):
            sanitizado, count = self._EMAIL_PATTERN.subn("[EMAIL_MASCARADO_LGPD]", sanitizado)
            total += count
            tipos_detectados.append("EMAIL")

        if self._PHONE_PATTERN.search(sanitizado):
            sanitizado, count = self._PHONE_PATTERN.subn("[TELEFONE_MASCARADO_LGPD]", sanitizado)
            total += count
            tipos_detectados.append("PHONE")

        return PIIMaskingResult(
            texto_sanitizado=sanitizado,
            tipos_detectados=tipos_detectados,
            total_substituicoes=total,
        )


_PII_GLOBAL = PIIMasker()


def mascarar_pii(texto: str) -> str:
    """Função utilitária rápida para higienização de strings."""
    return _PII_GLOBAL.mascarar(texto).texto_sanitizado
