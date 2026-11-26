"""Rotas HTTP para unidades geolocalizadas e estoque CEAF-DF (InfoSaúde-DF)."""

from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException, Query, status

from app.api.schemas.erro import ErroDTO
from app.application.pharmacy_stock import (
    CeafStockResponseDTO,
    NearbyPharmaciesResponseDTO,
    PharmacyStockRepositoryPort,
)
from app.container import get_services
from app.infrastructure.persistence.repositories.pharmacy_stock_repository import (
    LocalPharmacyStockRepository,
)

router = APIRouter(prefix="/api/v1", tags=["pharmacies"])


def _stock_repo() -> PharmacyStockRepositoryPort:
    return get_services().pharmacy_stock_repo or LocalPharmacyStockRepository()


@router.get(
    "/pharmacies/nearby",
    response_model=NearbyPharmaciesResponseDTO,
    responses={422: {"model": ErroDTO, "description": "Coordenadas ou parâmetros inválidos"}},
)
def nearby_pharmacies(
    ra: str = Query(default="", max_length=150, description="Região Administrativa (RA) no DF"),
    q: str = Query(default="", max_length=150, description="Filtro por nome, tipo ou endereço"),
    lat: float | None = Query(default=None, ge=-90.0, le=90.0, description="Latitude decimal"),
    lng: float | None = Query(default=None, ge=-180.0, le=180.0, description="Longitude decimal"),
    limite: int = Query(default=8, ge=1, le=25),
) -> NearbyPharmaciesResponseDTO:
    """Lista unidades públicas e farmácias do DF próximas ou associadas à RA."""
    if (lat is not None and not math.isfinite(lat)) or (lng is not None and not math.isfinite(lng)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Coordenadas lat/lng devem ser números finitos.",
        )
    if (lat is None) != (lng is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Informe lat e lng juntos ao filtrar por GPS.",
        )
    guardrail = get_services().guardrail
    ra_segura = guardrail.desidentificar_dados_pessoais(ra).texto_sanitizado if ra else ""
    return _stock_repo().find_nearby(ra=ra_segura, q=q, lat=lat, lng=lng, limite=limite)


@router.get("/ceaf-stock", response_model=CeafStockResponseDTO)
def ceaf_stock(
    q: str = Query(default="", max_length=150, description="Medicamento ou termo de busca DCB"),
    unidade: str = Query(
        default="", max_length=80, description="Polo CEAF (Asa Sul, Ceilândia ou Gama)"
    ),
    limite: int = Query(default=15, ge=1, le=50),
) -> CeafStockResponseDTO:
    """Consulta o último snapshot InfoSaúde-DF de estoque do Alto Custo (CEAF-DF)."""
    guardrail = get_services().guardrail
    q_seguro = guardrail.desidentificar_dados_pessoais(q).texto_sanitizado if q else ""
    unidade_segura = (
        guardrail.desidentificar_dados_pessoais(unidade).texto_sanitizado if unidade else ""
    )
    return _stock_repo().query_ceaf_stock(q=q_seguro, unidade=unidade_segura, limite=limite)
