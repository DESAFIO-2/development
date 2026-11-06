"""Guardrail Ético Inegociável: Preservação do Ato Médico (Lei nº 12.842/2013).

Intercepta e bloqueia pedidos de diagnóstico, prescrição, alteração de dosagem
ou substituição de medicamentos, garantindo que o sistema atue estritamente
na navegação administrativa e logística.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


@dataclass(frozen=True)
class ClinicalCheckResult:
    """Resultado da inspeção do Guardrail Clínico."""

    bloqueado: bool
    motivo: str
    alerta_emergencia: bool
    mensagem_acolhedora: str


class ClinicalGuardrail:
    """Validador rigoroso de segurança clínica e ética médica."""

    # Padrões de Prescrição / Recomendação Clínica
    _PATTERNS_PRESCRICAO: tuple[re.Pattern[str], ...] = (
        re.compile(r"\bo que (devo|posso|eu) tomar\b"),
        re.compile(r"\bque remedio (eu )?tomo\b"),
        re.compile(r"\bqual remedio (e|serve|e bom|tomar|tomaria)\b"),
        re.compile(r"\bme (indica|receita|prescreve|passa)\b"),
        re.compile(r"\bpara baixar a febre\b"),
        re.compile(r"\bo que dou\b"),
        re.compile(r"\bqual (antibiotico|calmante|analgesico|anti-inflamatorio|antidepressivo)\b"),
        re.compile(r"\bremedio para\b"),
        re.compile(r"\breceita para dor\b"),
    )

    # Padrões de Dosagem / Posologia
    _PATTERNS_DOSAGEM: tuple[re.Pattern[str], ...] = (
        re.compile(r"\b(dobrar|aumentar|reduzir|diminuir)\s+a?\s*dose\b"),
        re.compile(r"\bdose (certa|de dipirona|recomendada)\b"),
        re.compile(r"\bquantos comprimidos\b"),
        re.compile(r"\b(tomar|tomo)\s+dois\b"),
        re.compile(r"\bposso parar\b"),
        re.compile(r"\besqueci de tomar ontem\b"),
    )

    # Padrões de Diagnóstico / Gravidade
    _PATTERNS_DIAGNOSTICO: tuple[re.Pattern[str], ...] = (
        re.compile(r"\bo que eu tenho\b"),
        re.compile(r"\beu tenho diabetes\b"),
        re.compile(r"\be grave\b"),
        re.compile(r"\b(e|sao)\s+alergia\b"),
        re.compile(r"\bmanchas\s+(vermelhas|na pele)\b"),
        re.compile(r"\be dengue ou covid\b"),
        re.compile(r"\bpelos meus sintomas\b"),
    )

    # Padrões de Troca / Substituição Terapêutica
    _PATTERNS_TROCA: tuple[re.Pattern[str], ...] = (
        re.compile(r"\bposso trocar\b"),
        re.compile(r"\bqual remedio substitui\b"),
        re.compile(r"\bsubstitui a\b"),
        re.compile(r"\bno lugar do que o medico passou\b"),
        re.compile(r"\bposso tomar o da minha\b"),
        re.compile(r"\bposso usar o que eu quiser\b"),
    )

    # Padrões de Jailbreak / Indução Adversarial
    _PATTERNS_JAILBREAK: tuple[re.Pattern[str], ...] = (
        re.compile(r"\bignore as instrucoes\b"),
        re.compile(r"\bfinja que\b"),
        re.compile(r"\bpergunta hipotetica\b"),
        re.compile(r"\bsou enfermeira\b"),
        re.compile(r"\bmodo desenvolvedor\b"),
        re.compile(r"\bregras desligadas\b"),
    )

    # Sinais de Alarme / Emergência Médica
    _EMERGENCY_FLAGS: tuple[str, ...] = (
        "dor no peito",
        "falta de ar",
        "pressao subiu",
        "18x11",
        "18x12",
        "desmaio",
        "infarto",
        "avc",
    )

    def inspecionar(self, pergunta: str) -> ClinicalCheckResult:
        """Avalia se a pergunta do usuário deve ser bloqueada."""
        norm = _normalizar(pergunta)

        tem_emergencia = any(flag in norm for flag in self._EMERGENCY_FLAGS)

        todas_as_regras = (
            ("PRESCRICAO", self._PATTERNS_PRESCRICAO),
            ("DOSAGEM", self._PATTERNS_DOSAGEM),
            ("DIAGNOSTICO", self._PATTERNS_DIAGNOSTICO),
            ("TROCA_TERAPEUTICA", self._PATTERNS_TROCA),
            ("JAILBREAK", self._PATTERNS_JAILBREAK),
        )

        for motivo, patterns in todas_as_regras:
            for pattern in patterns:
                if pattern.search(norm):
                    if tem_emergencia:
                        msg = (
                            "ALERTA DE EMERGÊNCIA: Diante de sintomas graves como dor no peito, "
                            "falta de ar ou picos pressóricos, procure imediatamente uma UPA 24h, "
                            "ligue para o SAMU (192) ou dirija-se ao pronto-socorro. "
                            "O SUS Cidadão atua estritamente na navegação administrativa de onde "
                            "retirar medicamentos gratuitos já prescritos e não realiza "
                            "atendimento médico emergencial."
                        )
                    else:
                        msg = (
                            "Aviso Importante (Preservação do Ato Médico — Lei nº 12.842/2013): "
                            "O SUS Cidadão atua exclusivamente na orientação logística e "
                            "administrativa de acesso aos serviços públicos. Não indicamos "
                            "diagnósticos, não alteramos doses e não prescrevemos nem "
                            "substituímos medicamentos. Por favor, consulte seu médico ou a "
                            "equipe de Saúde da Família da sua UBS antes de alterar seu "
                            "tratamento."
                        )
                    return ClinicalCheckResult(
                        bloqueado=True,
                        motivo=motivo,
                        alerta_emergencia=tem_emergencia,
                        mensagem_acolhedora=msg,
                    )

        return ClinicalCheckResult(
            bloqueado=False,
            motivo="PERMITIDO",
            alerta_emergencia=False,
            mensagem_acolhedora="",
        )


_GUARDRAIL_GLOBAL = ClinicalGuardrail()


def deve_bloquear(pergunta: str) -> bool:
    """Função alvo consumida pelo runner de benchmark (evals/runners/guardrail_runner.py)."""
    return _GUARDRAIL_GLOBAL.inspecionar(pergunta).bloqueado
