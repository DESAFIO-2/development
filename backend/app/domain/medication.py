from enum import StrEnum


class CoverageRoute(StrEnum):
    """Via oficial de obtenção gratuita do medicamento no SUS / DF."""

    FARMACIA_POPULAR = "FARMACIA_POPULAR"
    UBS_REME_DF = "UBS_REME_DF"
    FARMACIA_ALTO_CUSTO = "FARMACIA_ALTO_CUSTO"
    SISREG_EXAME_CONSULTA = "SISREG_EXAME_CONSULTA"
    HOSPITALAR = "HOSPITALAR"
    NAO_PADRONIZADO = "NAO_PADRONIZADO"
