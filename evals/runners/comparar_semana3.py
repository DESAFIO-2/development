"""Contrato inicial do experimento pareado LLM sem recuperação × LLM com RAG."""

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

from app.application.ports import RetrievalHitDTO, RetrieverPort

Gerador = Callable[[str, tuple[RetrievalHitDTO, ...]], str]


@dataclass(frozen=True)
class RespostaExperimental:
    caso_id: str
    variante: Literal["llm_sem_recuperacao", "llm_com_rag"]
    pergunta: str
    referencia: str
    resposta: str
    evidencias: tuple[RetrievalHitDTO, ...]


def comparar_caso(
    *,
    caso_id: str,
    pergunta: str,
    referencia: str,
    gerar: Gerador,
    retriever: RetrieverPort,
    top_k: int = 3,
) -> tuple[RespostaExperimental, RespostaExperimental]:
    """Gera o par com o mesmo adaptador; só o braço RAG recebe evidências."""
    evidencias = tuple(retriever.search(pergunta, top_k=top_k))
    return (
        RespostaExperimental(
            caso_id,
            "llm_sem_recuperacao",
            pergunta,
            referencia,
            gerar(pergunta, ()),
            (),
        ),
        RespostaExperimental(
            caso_id,
            "llm_com_rag",
            pergunta,
            referencia,
            gerar(pergunta, evidencias),
            evidencias,
        ),
    )
