"""Normalização de texto antes de qualquer verificação.

Atacantes escondem comandos com caracteres invisíveis, letras de outros
alfabetos ou letras espaçadas. Normalizar primeiro faz o detector ver o
que o LLM vai ver.
"""

import re
import unicodedata

# Espaços, tabs e quebras de linha repetidos viram um espaço só.
_ESPACOS = re.compile(r"\s+")
# "i g n o r e", "i.g.n.o.r.e", "i-g-n-o-r-e": 4 ou mais letras soltas em sequência.
_LETRAS_ESPACADAS = re.compile(r"\b(?:\w[\s.\-_*]){3,}\w\b")
_LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)


def contar_invisiveis(texto: str) -> int:
    """Quantos caracteres invisíveis (zero-width, bidi, BOM: categoria Unicode Cf) há no texto."""
    return sum(1 for caractere in texto if unicodedata.category(caractere) == "Cf")


def limpar(texto: str) -> str:
    """Versão segura para seguir no fluxo: NFKC, sem invisíveis, espaços únicos."""
    normalizado = unicodedata.normalize("NFKC", texto)
    sem_invisiveis = "".join(c for c in normalizado if unicodedata.category(c) != "Cf")
    return _ESPACOS.sub(" ", sem_invisiveis).strip()


def forma_de_comparacao(texto: str) -> str:
    """Versão só para casar padrões: minúscula, sem acento, sem leet, letras juntadas."""
    base = limpar(texto).lower()
    sem_acento = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    sem_leet = sem_acento.translate(_LEET)
    return _LETRAS_ESPACADAS.sub(lambda m: re.sub(r"[\s.\-_*]", "", m.group()), sem_leet)
