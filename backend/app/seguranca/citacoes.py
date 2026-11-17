"""Citação por ID (protocolo `semana3-v3`): o modelo cita o ID, o código completa.

Na coleta de 12/11 só 1 de 18 respostas citou no formato completo: o modelo
acertava o ID do chunk, mas errava título e página. Copiar título e página é
trabalho do código, que tem os metadados exatos da busca.

- `expandir_citacoes` troca `[CHK-A]` por `[Fonte: CHK-A | título, p. N]`. Um ID que a
  busca não devolveu vira `[Fonte: CHK-X | FORA_DO_CONTEXTO]`: continua visível para
  a validação de saída barrar, em vez de sumir.
- `remover_citacoes` tira os marcadores antes do juiz RAGAS (`ragas_v2`): citação é
  medida à parte, por regra (`citacao_metadados_valida`), não pelo juiz.

Só depende da biblioteca padrão: o ambiente isolado de avaliação também importa daqui.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Protocol

ROTULO_FORA_DO_CONTEXTO = "FORA_DO_CONTEXTO"
_ID = r"CHK-[A-Za-z0-9][A-Za-z0-9_-]*"
# "[CHK-A]", "[CHK-A, CHK-B]" ou "[CHK-A; CHK-B]".
CITACAO_POR_ID = re.compile(rf"\[\s*({_ID}(?:\s*[,;]\s*{_ID})*)\s*\]")
_FONTE_COMPLETA = re.compile(r"\[\s*fonte\s*:[^\]]*\]", re.IGNORECASE)
_ESPACO_ANTES_PONTUACAO = re.compile(r"\s+([.,;:!?])")
_ESPACOS = re.compile(r"[ \t]{2,}")


class Evidencia(Protocol):
    @property
    def chunk_id(self) -> str: ...

    @property
    def document_title(self) -> str: ...

    @property
    def page_number(self) -> int: ...


def ids_citados(texto: str) -> list[str]:
    """IDs citados no formato curto, na ordem em que aparecem."""
    return [
        chunk_id.strip()
        for grupo in CITACAO_POR_ID.finditer(texto)
        for chunk_id in re.split(r"[,;]", grupo.group(1))
    ]


def expandir_citacoes(texto: str, evidencias: Iterable[Evidencia]) -> tuple[str, dict[str, int]]:
    """Completa cada `[CHK-ID]` com título e página e devolve a contagem por situação."""
    por_id = {hit.chunk_id: hit for hit in evidencias}
    contagem = {"validas": 0, "fora_do_contexto": 0}

    def completar(grupo: re.Match[str]) -> str:
        partes = []
        for chunk_id in (c.strip() for c in re.split(r"[,;]", grupo.group(1))):
            hit = por_id.get(chunk_id)
            if hit is None:
                contagem["fora_do_contexto"] += 1
                partes.append(f"[Fonte: {chunk_id} | {ROTULO_FORA_DO_CONTEXTO}]")
            else:
                contagem["validas"] += 1
                partes.append(f"[Fonte: {chunk_id} | {hit.document_title}, p. {hit.page_number}]")
        return " ".join(partes)

    return CITACAO_POR_ID.sub(completar, texto), contagem


def remover_citacoes(texto: str) -> str:
    """Texto sem marcadores de citação (completos ou curtos), para o juiz RAGAS."""
    sem_fontes = _FONTE_COMPLETA.sub("", texto)
    sem_ids = CITACAO_POR_ID.sub("", sem_fontes)
    sem_espaco = _ESPACO_ANTES_PONTUACAO.sub(r"\1", sem_ids)
    return "\n".join(_ESPACOS.sub(" ", linha).strip() for linha in sem_espaco.splitlines()).strip()
