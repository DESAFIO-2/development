"""Correspondência determinística de Denominação Comum Brasileira (DCB) na base Gold."""

from __future__ import annotations

from app.application.ports import CanonicalMedicationItem
from app.retrieval.text_normalizer import normalizar_texto_pt


class TabularDCBMatcher:
    """Busca determinística e fuzzy ponderada por sobreposição de termos de princípios ativos."""

    _IGNORED_SALTS: frozenset[str] = frozenset(
        {
            "cloridrato",
            "maleato",
            "besilato",
            "sulfato",
            "fumarato",
            "hemifumarato",
            "potassica",
            "sodica",
            "sodico",
            "calcica",
            "hidratada",
            "di",
            "hidratado",
            "humana",
            "mg",
            "mcg",
            "ui",
            "ml",
        }
    )

    def __init__(self, medications: list[CanonicalMedicationItem]) -> None:
        self.medications = medications

    def casar(self, consulta: str) -> list[tuple[float, CanonicalMedicationItem]]:
        """Retorna medicamentos canônicos casados com a consulta e score em [0, 1]."""
        norm_query = normalizar_texto_pt(consulta)
        query_tokens = set(norm_query.split())
        matches: list[tuple[float, CanonicalMedicationItem]] = []

        for med in self.medications:
            norm_dcb = normalizar_texto_pt(med.dcb_name)
            dcb_tokens = [t for t in norm_dcb.split() if len(t) > 2]
            core_tokens = [t for t in dcb_tokens if t not in self._IGNORED_SALTS] or dcb_tokens
            if not core_tokens:
                continue

            if norm_dcb in norm_query:
                score = 0.95
            else:
                matched_core = [t for t in core_tokens if t in query_tokens]
                if len(matched_core) < len(core_tokens):
                    continue
                coverage = len(matched_core) / len(core_tokens)
                score = 0.70 + 0.25 * coverage

            norm_conc = normalizar_texto_pt(med.concentration)
            if norm_conc and norm_conc in norm_query:
                score = min(1.0, score + 0.05)

            matches.append((round(score, 4), med))

        matches.sort(key=lambda item: item[0], reverse=True)

        # Deduplica por dcb_name mantendo maior score
        vistos: set[str] = set()
        unicos: list[tuple[float, CanonicalMedicationItem]] = []
        for score, med in matches:
            if med.dcb_name not in vistos:
                vistos.add(med.dcb_name)
                unicos.append((score, med))

        return unicos


__all__ = ["CanonicalMedicationItem", "TabularDCBMatcher"]
