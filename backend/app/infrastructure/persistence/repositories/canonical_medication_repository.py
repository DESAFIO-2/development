"""Repositório concreto de medicamentos canônicos (Gold Layer)."""

from __future__ import annotations

import json
from pathlib import Path

from app.application.ports import MedicationRepositoryPort
from app.core.config import settings
from app.retrieval.tabular_matcher import CanonicalMedicationItem
from app.retrieval.text_normalizer import normalizar_texto_pt


class LocalCanonicalMedicationRepository(MedicationRepositoryPort):
    """Carrega o catálogo canônico de medicamentos a partir do arquivo JSON na camada processed."""

    def __init__(self, json_path: Path | None = None) -> None:
        path = (
            json_path
            if json_path is not None
            else settings.data_processed_dir / "medicamentos_sus_canonical.json"
        )
        conteudo = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(conteudo, list) or not conteudo:
            raise ValueError(f"Corpus precisa conter uma lista não vazia: {path}")
        self._itens = [CanonicalMedicationItem.from_dict(item) for item in conteudo]

    def listar_todos(self) -> list[CanonicalMedicationItem]:
        return list(self._itens)

    def buscar_por_dcb(self, dcb_nome: str) -> list[CanonicalMedicationItem]:
        norm = normalizar_texto_pt(dcb_nome)
        return [med for med in self._itens if norm in normalizar_texto_pt(med.dcb_name)]

    def sugerir_autocomplete(self, termo: str, limite: int = 10) -> list[CanonicalMedicationItem]:
        norm = normalizar_texto_pt(termo)
        if not norm:
            return self._itens[:limite]

        sugestoes: list[tuple[int, CanonicalMedicationItem]] = []
        for med in self._itens:
            dcb_norm = normalizar_texto_pt(med.dcb_name)
            if dcb_norm.startswith(norm):
                sugestoes.append((0, med))
            elif norm in dcb_norm:
                sugestoes.append((1, med))

        sugestoes.sort(key=lambda x: (x[0], x[1].dcb_name))
        return [item[1] for item in sugestoes[:limite]]
