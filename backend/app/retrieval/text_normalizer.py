"""Normalização e tokenização textual determinística para recuperação em saúde pública."""

from __future__ import annotations

import re
import unicodedata

PT_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "ao",
        "aos",
        "as",
        "com",
        "como",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "esta",
        "este",
        "meu",
        "minha",
        "na",
        "nas",
        "no",
        "nos",
        "o",
        "onde",
        "os",
        "ou",
        "para",
        "pela",
        "pelas",
        "pelo",
        "pelos",
        "por",
        "qual",
        "que",
        "se",
        "sem",
        "ser",
        "seu",
        "sua",
        "um",
        "uma",
    }
)


def normalizar_texto_pt(texto: str) -> str:
    """Remove acentuação, converte para minúsculas e preserva termos farmacêuticos."""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    sem_acento = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    limpo = re.sub(r"[^a-z0-9\s/]", " ", sem_acento)
    return " ".join(limpo.split())


def tokenizar_com_ngrams(texto: str, max_ngram: int = 2) -> list[str]:
    """Tokeniza texto normalizado removendo stopwords e gerando n-gramas (1..max_ngram)."""
    norm = normalizar_texto_pt(texto)
    base_tokens = [tok for tok in norm.split() if len(tok) > 1 and tok not in PT_STOPWORDS]
    tokens = list(base_tokens)
    if max_ngram >= 2 and len(base_tokens) >= 2:
        for idx in range(len(base_tokens) - 1):
            tokens.append(f"{base_tokens[idx]}_{base_tokens[idx + 1]}")
    return tokens


# Aliases de compatibilidade
normalize_pt_text = normalizar_texto_pt
tokenize_with_ngrams = tokenizar_com_ngrams
