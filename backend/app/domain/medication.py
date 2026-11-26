from enum import StrEnum


class CoverageRoute(StrEnum):
    """Via oficial de obtenção gratuita do medicamento no SUS / DF."""

    FARMACIA_POPULAR = "FARMACIA_POPULAR"
    UBS_REME_DF = "UBS_REME_DF"
    FARMACIA_ALTO_CUSTO = "FARMACIA_ALTO_CUSTO"
    SISREG_EXAME_CONSULTA = "SISREG_EXAME_CONSULTA"
    HOSPITALAR = "HOSPITALAR"
    NAO_PADRONIZADO = "NAO_PADRONIZADO"


_ROUTE_BY_DISPENSATION: dict[str, CoverageRoute] = {
    "FARMACIA_POPULAR": CoverageRoute.FARMACIA_POPULAR,
    "ALTO_CUSTO_CEAF": CoverageRoute.FARMACIA_ALTO_CUSTO,
    "UBS_ATENCAO_PRIMARIA": CoverageRoute.UBS_REME_DF,
    "HOSPITALAR": CoverageRoute.HOSPITALAR,
}


def route_from_dispensation(dispensation_route: str) -> CoverageRoute:
    """Converte a rota de dispensação do catálogo canônico para CoverageRoute."""
    return _ROUTE_BY_DISPENSATION.get(dispensation_route, CoverageRoute.NAO_PADRONIZADO)
