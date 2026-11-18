"""Validação de contexto com exceções documentais restritas ao corpus carregado."""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.application.ports import RetrievalHitDTO
from app.seguranca.esteira import Canal, inspecionar_entrada
from app.seguranca.saida import validar_saida

_CID_NORMATIVO = re.compile(r"\bCID(?:-?10)?\s+[A-TV-Z]\d{2}(?:\.\d{1,2})?", re.I)
_SEI = re.compile(r"\bSEI\s+n[º°o]\s*\d{8,9}\b", re.I)


def _identity(hit: RetrievalHitDTO) -> tuple[str, str, str, int, str, str]:
    return (hit.chunk_id, hit.source_id, hit.document_title, hit.page_number, hit.section, hit.text)


def extract_public_processes(texts: Iterable[str]) -> tuple[str, ...]:
    """Extrai referências públicas SEI exatas presentes no corpus institucional carregado."""
    encontrados = {
        match.group(0).strip() for text in texts if text for match in _SEI.finditer(text)
    }
    return tuple(sorted(encontrados, key=len, reverse=True))


class PublicContextRegistry:
    """Correspondência exata de identidade + conteúdo; nunca confiar só no ID."""

    def __init__(
        self,
        approved: Iterable[RetrievalHitDTO] = (),
        *,
        public_processes: Iterable[str] = (),
    ) -> None:
        self._approved = frozenset(_identity(hit) for hit in approved)
        self._public_processes = tuple(
            sorted(
                {proc.strip() for proc in public_processes if _SEI.fullmatch(proc.strip())},
                key=len,
                reverse=True,
            )
        )

    def scrub_approved_processes(self, text: str) -> str:
        """Substitui apenas processos SEI públicos previamente carregados do catálogo."""
        result = text
        for proc in self._public_processes:
            if proc in result:
                result = result.replace(proc, "[PROCESSO_PUBLICO]")
        return result

    def validation_text(self, hit: RetrievalHitDTO) -> str:
        text = hit.text
        if _identity(hit) in self._approved:
            # Só códigos de classificação/processo. Não excluir nomes, CPF, CNS,
            # telefones ou e-mail, nem suprimir orientação de dose/injeção.
            text = _CID_NORMATIVO.sub("[CODIGO_NORMATIVO]", text)
            text = _SEI.sub("[PROCESSO_PUBLICO]", text)
        return text

    def approved(self, hit: RetrievalHitDTO) -> bool:
        return all(
            not inspecionar_entrada(text, Canal.PDF).bloqueado and validar_saida(text).aprovada
            for text in (self.validation_text(hit), hit.document_title, hit.section)
        )


def build_public_context(
    approved: Iterable[RetrievalHitDTO] = (),
    *,
    catalog_texts: Iterable[str] = (),
) -> PublicContextRegistry:
    """Constrói o registro único de exceções documentais a partir do corpus estático."""
    hits = tuple(approved)
    processes = extract_public_processes([*(hit.text for hit in hits), *catalog_texts])
    return PublicContextRegistry(hits, public_processes=processes)
