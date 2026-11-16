"""Correspondência determinística de Denominação Comum Brasileira (DCB) na base Gold."""

from __future__ import annotations

import re

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

    _DOSE_PART = (
        r"\b\d+(?:[.,]\d+)*(?:/\d+(?:[.,]\d+)*)*\s*"
        r"(?:mcg|mg|g|ui|ml|%)(?!\w)"
        r"(?:\s*/\s*(?:\d+(?:[.,]\d+)*\s*)?(?:ml|g|dose)\b)?"
    )
    _DOSE = re.compile(_DOSE_PART + r"(?:\s*\+\s*" + _DOSE_PART + r")*", re.IGNORECASE)

    _EQUIVALENCIAS_CONCENTRACAO_SCOPED: dict[str, tuple[frozenset[str], ...]] = {
        "sacubitril valsartana sodica hidratada": (
            frozenset({"97mg+103mg", "200mg"}),
            frozenset({"49mg+51mg", "100mg"}),
            frozenset({"24mg+26mg", "50mg"}),
        ),
        "sulfato de salbutamol": (frozenset({"100mcg", "100mcg/dose"}),),
    }

    @staticmethod
    def normalizar_concentracao(concentracao: str) -> str:
        # Remove separador de milhar brasileiro (5.000, 1.000) preservando decimais (0.25).
        sem_milhar = re.sub(
            r"(?<![\d.,])([1-9]\d{0,2}(?:\.\d{3})+)(?![\d.,])",
            lambda m: m.group(1).replace(".", ""),
            concentracao,
        )
        valor = re.sub(r"\s+", "", sem_milhar.lower().replace(",", "."))
        # Abreviação de composição (97/103 mg), sem somar doses ou converter unidades.
        composto = re.fullmatch(r"(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)(mcg|mg|g|ui)", valor)
        if composto:
            primeiro, segundo, unidade = composto.groups()
            return f"{primeiro}{unidade}+{segundo}{unidade}"
        return valor

    @classmethod
    def _doses_equivalentes(cls, norm_dcb: str, dose_consulta: str, dose_catalogo: str) -> bool:
        if not dose_consulta or dose_consulta == dose_catalogo:
            return True
        pares = cls._EQUIVALENCIAS_CONCENTRACAO_SCOPED.get(norm_dcb, ())
        return any(dose_consulta in par and dose_catalogo in par for par in pares)

    @classmethod
    def doses_no_texto(cls, texto: str) -> set[str]:
        return {cls.normalizar_concentracao(dose) for dose in cls._DOSE.findall(texto)}

    @classmethod
    def tem_numero_nao_interpretado(cls, texto: str) -> bool:
        """Número sem unidade reconhecida exige confirmação da apresentação."""
        residual = cls._DOSE.sub("", texto)
        residual = re.sub(r"\bdiabetes\s+tipo\s+[12]\b", "", residual, flags=re.IGNORECASE)
        # Quantidade de embalagem não é uma segunda concentração. Só aceitar
        # números administrativos explicitamente identificados; nunca descartar
        # o resto de uma composição porque a primeira dose foi reconhecida.
        residual = re.sub(
            r"\b\d+\s*(?:comprimidos|capsulas|cápsulas|ampolas|unidades)\b",
            "",
            residual,
            flags=re.IGNORECASE,
        )
        return bool(re.search(r"\d", residual))

    def __init__(self, medications: list[CanonicalMedicationItem]) -> None:
        self.medications = medications

    def casar(
        self, consulta: str, *, concentracao: str = "", forma: str = "", deduplicar: bool = True
    ) -> list[tuple[float, CanonicalMedicationItem]]:
        """Retorna medicamentos canônicos casados com a consulta e score em [0, 1]."""
        norm_query = normalizar_texto_pt(consulta)
        query_tokens = set(norm_query.split())
        matches: list[tuple[float, CanonicalMedicationItem]] = []

        dose = self.normalizar_concentracao(concentracao)
        forma_norm = normalizar_texto_pt(forma)

        for med in self.medications:
            norm_dcb = normalizar_texto_pt(med.dcb_name)
            if not self._doses_equivalentes(
                norm_dcb, dose, self.normalizar_concentracao(med.concentration)
            ):
                continue
            if forma_norm and normalizar_texto_pt(med.pharmaceutical_form) != forma_norm:
                continue
            dcb_tokens = [t for t in norm_dcb.split() if len(t) > 2]
            core_tokens = [t for t in dcb_tokens if t not in self._IGNORED_SALTS] or dcb_tokens
            if not core_tokens:
                continue

            if f" {norm_dcb} " in f" {norm_query} ":
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

        if not deduplicar:
            return matches

        # Deduplica por dcb_name mantendo maior score
        vistos: set[str] = set()
        unicos: list[tuple[float, CanonicalMedicationItem]] = []
        for score, med in matches:
            if med.dcb_name not in vistos:
                vistos.add(med.dcb_name)
                unicos.append((score, med))

        return unicos


__all__ = ["CanonicalMedicationItem", "TabularDCBMatcher"]
