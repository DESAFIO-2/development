"""Baseline ingênuo do guardrail clínico: bloqueia por palavras-chave.

Serve de régua mínima. O guardrail de verdade (backend/app/guardrails) precisa
ser melhor que isto no mesmo dataset.
"""

import unicodedata

GATILHOS = (
    "o que devo tomar",
    "que remedio eu tomo",
    "qual remedio",
    "me indica",
    "dose",
    "dobrar",
    "quantos comprimidos",
    "posso parar",
    "posso trocar",
    "substitui",
    "no lugar",
    "o que eu tenho",
    "e grave",
    "ignore as instrucoes",
    "finja que",
    "receita para",
)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def deve_bloquear(pergunta: str) -> bool:
    texto = _normalizar(pergunta)
    return any(gatilho in texto for gatilho in GATILHOS)
