"""Contratos e porta para consulta de farmácias geolocalizadas e estoque CEAF-DF."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

STALE_AFTER_HOURS = 48

AVISO_ESTOQUE_CEAF = (
    "Consulta cobre exclusivamente o estoque das farmácias de Alto Custo (CEAF-DF: Asa Sul, "
    "Ceilândia e Gama) no último snapshot coletado do painel InfoSaúde-DF. "
    "Unidades Básicas de Saúde (UBS / REME-DF) ainda não possuem consulta geral de estoque ao vivo."
)


class PharmacyLocationDTO(BaseModel):
    """Estabelecimento público de dispensação / farmácia no DF."""

    cnes: str
    name: str
    address: str
    neighborhood_or_ra: str
    pharmacy_type: str
    latitude: float | None = None
    longitude: float | None = None
    google_maps_url: str = ""
    covered_ras: list[str] | None = None
    distance_km: float | None = None


class NearbyPharmaciesResponseDTO(BaseModel):
    """Lista de unidades próximas ou compatíveis com a Região Administrativa."""

    ra: str
    total: int
    update_schedule: str | None = None
    items: list[PharmacyLocationDTO] = Field(default_factory=list)


class CeafStockItemDTO(BaseModel):
    """Disponibilidade de apresentação nas farmácias CEAF-DF."""

    cod_produto: str = ""
    desc_produto: str = ""
    unidade: str = ""
    disp_estoque: str = ""
    origem_abastecimento: str = ""
    psicotropico: str = ""
    ultima_atualizacao: str = ""
    updated_at: str | None = None
    stale_warning: bool = True


class CeafStockResponseDTO(BaseModel):
    """Resposta da consulta ao snapshot InfoSaúde-DF do Alto Custo (CEAF)."""

    query: str
    unidade: str
    updated_at: str | None = None
    synced_at_utc: str | None = None
    stale_warning: bool = True
    stale_after_hours: int = STALE_AFTER_HOURS
    cobertura_escopo: Literal["CEAF_ALTO_CUSTO"] = "CEAF_ALTO_CUSTO"
    cobertura_ubs_disponivel: bool = False
    aviso_cobertura: str = AVISO_ESTOQUE_CEAF
    total: int
    items: list[CeafStockItemDTO] = Field(default_factory=list)


class PharmacyStockRepositoryPort(Protocol):
    """Porta de leitura para estabelecimentos geolocalizados e estoque CEAF-DF."""

    def find_nearby(
        self,
        *,
        ra: str = "",
        q: str = "",
        lat: float | None = None,
        lng: float | None = None,
        limite: int = 8,
    ) -> NearbyPharmaciesResponseDTO: ...

    def query_ceaf_stock(
        self,
        *,
        q: str = "",
        unidade: str = "",
        limite: int = 15,
    ) -> CeafStockResponseDTO: ...
