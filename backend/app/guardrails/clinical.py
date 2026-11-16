"""Guardrail Ético Inegociável: Preservação do Ato Médico (Lei nº 12.842/2013).

Intercepta e bloqueia pedidos de diagnóstico, prescrição, alteração ou fracionamento
de dosagem, compartilhamento entre pessoas ou substituição terapêutica, usando regras
composicionais generalizáveis por intenção e papel semântico (ADR 0004).
"""

from __future__ import annotations

import re
import unicodedata

from app.application.ports import ClinicalCheckDTO
from app.seguranca.esteira import Canal, inspecionar_entrada

ClinicalCheckResult = ClinicalCheckDTO


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def _clausulas(texto_normalizado: str) -> list[str]:
    """Segmenta em cláusulas e remove pontuação residual para casar limites de palavra."""
    brutas = re.split(r"[.?!;\n]+", texto_normalizado)
    limpas: list[str] = []
    for cl in brutas:
        limpa = " ".join(re.sub(r"[^a-z0-9/\-\s]", " ", cl).split())
        if limpa:
            limpas.append(limpa)
    return limpas


_SUBST_TERAPEUTICO = (
    r"(?:remedio\w*|medicamento\w*|medicac\w*|comprimido\w*|capsula\w*|gota\w*|ampola\w*"
    r"|xarope\w*|pomada\w*|colirio\w*|antibiotic\w*|anti-?inflamatori\w*|analgesic\w*"
    r"|antidepressiv\w*|calmant\w*|vitamina\w*|suplemento\w*|cha\b|dose\w*|dosagem\b)"
)
_SINTOMA_OU_QUEIXA = (
    r"(?:dor(?:es)?|febre|gripe|resfriado|tosse|insonia|ansiedade|infeccao|inflamacao"
    r"|garganta|dente|cabeca|costas|enxaqueca|nausea\w*|vomito\w*|diarreia|alergia"
    r"|pressao|glicose|sintoma\w*)"
)
_FAMILIAR_TERCEIRO = (
    r"(?:filh[oa]|crianca|bebe|irmao|irma|mae|pai|avo\b|marido|esposa|vizinh[oa]"
    r"|parente|outra pessoa|alguem)"
)


class ClinicalGuardrail:
    """Validador composicional de segurança clínica e ética médica."""

    # Contexto administrativo explícito que nunca deve ser bloqueado como clínica
    _ADMINISTRATIVO_PERMITIDO: tuple[re.Pattern[str], ...] = (
        re.compile(r"\b(?:que horas?|horario)\b(?:\W+\w+){0,4}?\W+\b(?:tomo|tomar)\b"),
        re.compile(
            r"\b(?:jejum|beber agua|preparo)\b(?:\W+\w+){0,5}?\W+"
            r"\b(?:exame|hemograma|ultrassom|colesterol)\b"
        ),
        re.compile(
            r"\b(?:quantos? dias?|quando vence|renovar|renovacao|validade)\b"
            r"(?:\W+\w+){0,5}?\W+\breceita\b"
        ),
        re.compile(r"\besqueci\b(?:\W+\w+){0,4}?\W+\b(?:orientac\w*|documentos?|receita)\b"),
    )

    # 1. Prescrição / Recomendação para sintoma ou alvo clínico
    _PATTERNS_PRESCRICAO: tuple[re.Pattern[str], ...] = (
        re.compile(
            rf"\b(?:o que|qual|quais|que)\b(?:\W+\w+){{0,6}}?\W+"
            rf"\b(?:tomar|tomo|dar|dou|usar|uso|aplicar|aplico|serve|funciona|e bom|melhor)\b"
            rf"(?:\W+\w+){{0,6}}?\W+\b(?:{_SUBST_TERAPEUTICO}|{_SINTOMA_OU_QUEIXA})\b"
        ),
        re.compile(
            rf"\b(?:{_SINTOMA_OU_QUEIXA})\b(?:\W+\w+){{0,8}}?\W+"
            rf"\b(?:o que|qual|que)\b(?:\W+\w+){{0,4}}?\W+"
            r"\b(?:tomar|tomo|dar|dou|usar|uso|tomaria)\b"
        ),
        re.compile(
            rf"\b(?:me|nos|pode|poderia)\b(?:\W+\w+){{0,3}}?\W+"
            rf"\b(?:indica\w*|receit\w*|prescrev\w*|passa\w*|recomenda\w*)\b"
            rf"(?:\W+\w+){{0,6}}?\W+\b(?:{_SUBST_TERAPEUTICO}|{_SINTOMA_OU_QUEIXA})\b"
        ),
        re.compile(
            r"\b(?:qual|que)\b(?:\W+\w+){0,2}?\W+"
            r"\b(?:antibiotic\w*|anti-?inflamatori\w*|analgesic\w*|antidepressiv\w*|calmant\w*)\b"
        ),
    )

    # 2. Dosagem, fracionamento, compensação de esquecimento ou interrupção
    _PATTERNS_DOSAGEM: tuple[re.Pattern[str], ...] = (
        # Partir / dividir / quebrar / dobrar / ajustar / suspender medicamento ou dose
        re.compile(
            r"\b(?:partir|parto|parta|quebrar|quebro|dividir|divido|cortar|corto|amassar|abrir"
            r"|dobrar|dobro|duplicar|triplicar|aumentar|aumento|diminuir|diminuo|reduzir|reduzo"
            r"|repetir|repito|parar|paro|suspender|suspendo|interromper)\b"
            rf"(?:\W+\w+){{0,6}}?\W+\b(?:{_SUBST_TERAPEUTICO}|ao meio|no meio|metade|tratamento)\b"
        ),
        # Pergunta de quantidade ou cálculo individualizado por peso/idade
        re.compile(
            r"\b(?:quantos?|qual(?:\s+e)?|que)\b(?:\W+\w+){0,4}?\W+"
            r"\b(?:comprimido\w*|capsula\w*|gota\w*|dose\w*|dosagem|ml|mg)\b"
            r"(?:\W+\w+){0,6}?\W+\b(?:tomar|tomo|dar|dou|usar|uso|posso|devo|certa|ideal"
            r"|recomendad\w*|peso|kg|idade|crianca|adulto|por dia|ao dia)\b"
        ),
        # Compensar esquecimento, duplicidade ou dose múltipla ("faz mal tomar 2x / 2 comprimidos")
        re.compile(
            r"\b(?:tomar|tomei|tomo|usar|usei|dar|dei|tomaria)\b(?:\W+\w+){0,7}?\W+"
            r"\b(?:duas?\s+vezes|2\s*x|em\s+dobro|dobrad\w*|dois|duas|tres|a\s+mais|junto"
            r"|de\s+novo|novamente|atrasad\w*|ontem|de\s+uma\s+vez)\b"
        ),
        re.compile(
            r"\b(?:tomar|tomei|tomo|usar|usei|dar|dei|tomaria)\b(?:\W+\w+){0,4}?\W+"
            r"\b(?:\d+|dois|duas|tres)\s+(?:comprimido\w*|capsula\w*|gota\w*|dose\w*)\b"
            r"(?:\W+\w+){0,7}?\W+\b(?:de\s+uma\s+vez|junt[oa]s?|faz\s+mal|risco|perigo\w*"
            r"|problema|pode|posso|devo|hoje)\b"
        ),
        re.compile(
            r"\b(?:duas?\s+vezes|2\s*x|em\s+dobro|dobro|esqueci)\b(?:\W+\w+){0,7}?\W+"
            r"\b(?:tomo|tomar|comprimido|dose|remedio|faz\s+mal|problema|perigo\w*|hoje)\b"
        ),
        re.compile(
            r"\b(?:tomo|tomar|tomei|posso|devo|faz\s+mal|problema|perigo\w*)\b"
            r"(?:\W+\w+){0,4}?\W+\bmetade\b"
        ),
        re.compile(r"\bmetade\b(?:\W+\w+){0,5}?\W+\b(?:faz\s+mal|problema|perigo\w*|posso|devo)\b"),
    )

    # 3. Diagnóstico / interpretação de exames ou sintomas
    _PATTERNS_DIAGNOSTICO: tuple[re.Pattern[str], ...] = (
        re.compile(
            r"\b(?:o que\s+(?:eu\s+)?tenho|sera\s+que\s+(?:eu\s+)?tenho"
            r"|pelos?\s+(?:meus?\s+)?sintomas?)\b"
        ),
        re.compile(
            r"\b(?:eu\s+tenho|estou\s+com)\b(?:\W+\w+){0,5}?\W+"
            r"\b(?:diabetes|dengue|covid|doenca|alergia|infeccao|anemia|infarto|avc|grave)\b"
        ),
        re.compile(
            r"\b(?:meu\s+exame|exame\s+de|minha\s+glicose|minha\s+pressao|manchas?|caroco"
            r"|hemoglobina|resultado)\b(?:\W+\w+){0,7}?\W+"
            r"\b(?:e\s+grave|sao\s+alergia|e\s+alergia|diabetes|dengue|covid|doenca"
            r"|significa|indica)\b"
        ),
        re.compile(
            rf"\b(?:{_SINTOMA_OU_QUEIXA})\b(?:\W+\w+){{0,6}}?\W+"
            r"\b(?:e\s+(?:grave|alergia|dengue|covid|infarto|avc)|pode\s+ser\s+\w+)\b"
        ),
    )

    # 4. Troca terapêutica, compartilhamento entre pessoas ou substituição por suplemento
    _PATTERNS_TROCA: tuple[re.Pattern[str], ...] = (
        re.compile(
            r"\b(?:trocar|troco|substitu\w*|alternativa|equivalente|no\s+lugar\s+(?:de|do|da)"
            r"|em\s+vez\s+(?:de|do|da))\b(?:\W+\w+){0,7}?\W+"
            rf"\b(?:{_SUBST_TERAPEUTICO}|exame|tratamento|medico|receita|marca|jejum)\b"
        ),
        re.compile(
            r"\b(?:posso|pode|devo|consigo|quero)\b(?:\W+\w+){0,3}?\W+"
            r"\b(?:trocar|substituir|mudar)\b(?:\W+\w+){0,6}?\W+\b(?:pelo|pela|por)\b"
            r"(?!\W+(?:receita|cadastro|endereco|unidade|ubs|horario|comprovante|documento|conta)\b)"
        ),
        re.compile(
            rf"\b(?:{_SUBST_TERAPEUTICO}|exame)\b(?:\W+\w+){{0,6}}?\W+"
            r"\b(?:substitui\w*|troca\w*|no\s+lugar|em\s+vez)\b"
        ),
        # Compartilhamento de medicamento de terceiro / faixa etária diferente
        re.compile(
            rf"\b(?:{_FAMILIAR_TERCEIRO})\b(?:\W+\w+){{0,7}}?\W+"
            rf"\b(?:usar|tomar|dar|uso|tomo|dou)\b(?:\W+\w+){{0,6}}?\W+\b{_SUBST_TERAPEUTICO}\b"
        ),
        re.compile(
            rf"\b(?:usar|tomar|dar|uso|tomo|dou)\b(?:\W+\w+){{0,6}}?\W+\b{_SUBST_TERAPEUTICO}\b"
            rf"(?:\W+\w+){{0,6}}?\W+\b(?:do\s+{_FAMILIAR_TERCEIRO}|da\s+{_FAMILIAR_TERCEIRO}"
            r"|de\s+outra\s+pessoa|que\s+sobrou|parecido|o\s+que\s+eu\s+quiser)\b"
        ),
        # Falta do remédio -> substituir por vitamina / chá / outro item
        re.compile(
            r"\b(?:sem\s+o\s+remedio|sem\s+remedio|acabou\s+(?:o|meu)\s+remedio"
            r"|enquanto\s+nao\s+chega|faltou\s+o\s+remedio)\b(?:\W+\w+){0,8}?\W+"
            r"\b(?:uso|usar|tomo|tomar|vitamina\w*|cha\b|suplemento\w*|outro)\b"
        ),
    )

    # 5. Indução adversarial / quebra de escopo
    _PATTERNS_JAILBREAK: tuple[re.Pattern[str], ...] = (
        re.compile(
            r"\b(?:ignore|desconsidere|esqueca|anule)\b(?:\W+\w+){0,4}?\W+"
            r"\b(?:instruc\w*|regras?|limites?|filtros?|diretriz\w*)\b"
        ),
        re.compile(r"\b(?:finja|simule|atue)\b(?:\W+\w+){0,3}?\W+\b(?:que|ser|como)\b"),
        re.compile(r"\bpergunta\s+hipotetica\b"),
        re.compile(r"\bmodo\s+(?:desenvolvedor|dev|irrestrito|sem\s+filtro)\b"),
        re.compile(r"\bregras\s+desligadas\b"),
        re.compile(
            r"\b(?:sou|como)\b(?:\W+\w+){0,3}?\W+"
            r"\b(?:enfermeir\w*|medic\w*|farmaceutic\w*)\b(?:\W+\w+){0,6}?\W+"
            rf"\b(?:{_SUBST_TERAPEUTICO}|receit\w*|prescrev\w*|posologia)\b"
        ),
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

    _MSG_EMERGENCIA = (
        "ALERTA DE EMERGÊNCIA: Diante de sintomas graves como dor no peito, "
        "falta de ar ou picos pressóricos, procure imediatamente uma UPA 24h, "
        "ligue para o SAMU (192) ou dirija-se ao pronto-socorro. "
        "O SUS Cidadão atua estritamente na navegação administrativa de onde "
        "retirar medicamentos gratuitos já prescritos e não realiza "
        "atendimento médico emergencial."
    )
    _MSG_ATO_MEDICO = (
        "Aviso Importante (Preservação do Ato Médico — Lei nº 12.842/2013): "
        "O SUS Cidadão atua exclusivamente na orientação logística e "
        "administrativa de acesso aos serviços públicos. Não indicamos "
        "diagnósticos, não alteramos doses e não prescrevemos nem "
        "substituímos medicamentos. Por favor, consulte seu médico ou a "
        "equipe de Saúde da Família da sua UBS antes de alterar seu "
        "tratamento."
    )

    def _clausula_e_administrativa(self, clausula: str) -> bool:
        return any(p.search(clausula) for p in self._ADMINISTRATIVO_PERMITIDO)

    def inspecionar(self, pergunta: str) -> ClinicalCheckDTO:
        """Avalia se a pergunta do usuário deve ser bloqueada (Ato Médico + Anti-Injeção)."""
        check_injecao = inspecionar_entrada(pergunta, Canal.TEXTO)
        norm = _normalizar(pergunta)
        if any(flag in norm for flag in self._EMERGENCY_FLAGS):
            return ClinicalCheckDTO(
                bloqueado=True,
                motivo="EMERGENCIA_MEDICA",
                alerta_emergencia=True,
                mensagem_acolhedora=self._MSG_EMERGENCIA,
            )

        clausulas = _clausulas(norm) or [norm]

        todas_as_regras = (
            ("PRESCRICAO", self._PATTERNS_PRESCRICAO),
            ("DOSAGEM", self._PATTERNS_DOSAGEM),
            ("DIAGNOSTICO", self._PATTERNS_DIAGNOSTICO),
            ("TROCA_TERAPEUTICA", self._PATTERNS_TROCA),
            ("JAILBREAK", self._PATTERNS_JAILBREAK),
        )

        for clausula in clausulas:
            if self._clausula_e_administrativa(clausula):
                continue
            for motivo, patterns in todas_as_regras:
                if any(pattern.search(clausula) for pattern in patterns):
                    return ClinicalCheckDTO(
                        bloqueado=True,
                        motivo=motivo,
                        alerta_emergencia=False,
                        mensagem_acolhedora=self._MSG_ATO_MEDICO,
                    )

        if check_injecao.bloqueado:
            return ClinicalCheckDTO(
                bloqueado=True,
                motivo="PROMPT_INJECTION",
                alerta_emergencia=False,
                mensagem_acolhedora=(
                    "Aviso de Segurança (Preservação do Ato Médico — Lei nº 12.842/2013): "
                    "A solicitação contém instruções incompatíveis com o escopo de navegação "
                    "administrativa do SUS Cidadão. Informe apenas o nome do medicamento ou "
                    "exame prescrito para consultar as rotas oficiais de acesso gratuito."
                ),
            )

        return ClinicalCheckDTO(
            bloqueado=False,
            motivo="PERMITIDO",
            alerta_emergencia=False,
            mensagem_acolhedora="",
        )


_GUARDRAIL_GLOBAL = ClinicalGuardrail()


def deve_bloquear(pergunta: str) -> bool:
    """Função alvo consumida pelo runner de benchmark (evals/runners/guardrail_runner.py)."""
    return _GUARDRAIL_GLOBAL.inspecionar(pergunta).bloqueado
