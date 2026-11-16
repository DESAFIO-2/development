"""Adaptador concreto de GuardrailPort unificando ato médico e LGPD."""

from __future__ import annotations

from app.application.ports import ClinicalCheckDTO, GuardrailPort, PIIMaskingDTO
from app.guardrails.clinical import ClinicalGuardrail
from app.guardrails.pii import PIIMasker


class LocalGuardrailAdapter(GuardrailPort):
    """Implementação local determinística da porta de guardrails."""

    def __init__(
        self,
        clinical: ClinicalGuardrail | None = None,
        pii_masker: PIIMasker | None = None,
    ) -> None:
        self._clinical = clinical or ClinicalGuardrail()
        self._pii_masker = pii_masker or PIIMasker()

    def verificar_ato_medico(self, pergunta: str) -> ClinicalCheckDTO:
        return self._clinical.inspecionar(pergunta)

    def desidentificar_dados_pessoais(self, texto: str) -> PIIMaskingDTO:
        return self._pii_masker.mascarar(texto)
