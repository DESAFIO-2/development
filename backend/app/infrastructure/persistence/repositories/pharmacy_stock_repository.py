"""Repositório local para farmácias geolocalizadas e snapshot de estoque CEAF (InfoSaúde-DF)."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.application.pharmacy_stock import (
    STALE_AFTER_HOURS,
    CeafStockItemDTO,
    CeafStockResponseDTO,
    NearbyPharmaciesResponseDTO,
    PharmacyLocationDTO,
    PharmacyStockRepositoryPort,
)
from app.core.config import settings
from app.domain.stock_dates import parse_source_timestamp_utc
from app.retrieval.text_normalizer import normalizar_texto_pt


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distância geodésica aproximada em quilômetros entre duas coordenadas."""
    r_earth = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    return 2.0 * r_earth * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _is_snapshot_stale(updated_at_raw: str | None, *, now_utc: datetime | None = None) -> bool:
    if not updated_at_raw or not updated_at_raw.strip():
        return True
    try:
        parsed = datetime.fromisoformat(updated_at_raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    ref = now_utc or datetime.now(UTC)
    return parsed > ref or (ref - parsed) > timedelta(hours=STALE_AFTER_HOURS)


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


class LocalPharmacyStockRepository(PharmacyStockRepositoryPort):
    """Lê snapshots JSON de `df_pharmacies_geolocated.json` e `ceaf_live_stock.json`."""

    def __init__(self, data_dir: Path | None = None) -> None:
        base = data_dir if data_dir is not None else settings.data_processed_dir
        self._pharmacies_path = base / "df_pharmacies_geolocated.json"
        self._stock_path = base / "ceaf_live_stock.json"
        self._pharmacies_raw: dict[str, Any] | None = None
        self._stock_raw: dict[str, Any] | None = None

    def _load_pharmacies(self) -> dict[str, Any]:
        if self._pharmacies_raw is None:
            if not self._pharmacies_path.exists():
                self._pharmacies_raw = {"pharmacies": []}
            else:
                self._pharmacies_raw = json.loads(self._pharmacies_path.read_text(encoding="utf-8"))
        return self._pharmacies_raw

    def _load_stock(self) -> dict[str, Any]:
        if self._stock_raw is None:
            if not self._stock_path.exists():
                self._stock_raw = {"items": []}
            else:
                self._stock_raw = json.loads(self._stock_path.read_text(encoding="utf-8"))
        return self._stock_raw

    def find_nearby(
        self,
        *,
        ra: str = "",
        q: str = "",
        lat: float | None = None,
        lng: float | None = None,
        limite: int = 8,
    ) -> NearbyPharmaciesResponseDTO:
        raw = self._load_pharmacies()
        rows: list[dict[str, Any]] = list(raw.get("pharmacies", []))
        schedule = str(raw.get("update_schedule")) if raw.get("update_schedule") else None
        if not rows:
            return NearbyPharmaciesResponseDTO(
                ra=ra or "Distrito Federal",
                total=0,
                update_schedule=schedule,
                items=[],
            )

        clean_ra = normalizar_texto_pt(ra.replace(" - DF", ""))
        clean_q = normalizar_texto_pt(q)
        scored: list[tuple[float, PharmacyLocationDTO]] = []

        for row in rows:
            covered_raw = row.get("covered_ras")
            covered = (
                [str(x) for x in covered_raw if str(x).strip()]
                if isinstance(covered_raw, list)
                else None
            )
            hay = normalizar_texto_pt(
                " ".join(
                    [
                        str(row.get("name", "")),
                        str(row.get("address", "")),
                        str(row.get("neighborhood_or_ra", "")),
                        str(row.get("pharmacy_type") or ""),
                        " ".join(covered or []),
                    ]
                )
            )
            score = 0.0
            if clean_ra:
                if clean_ra not in hay:
                    continue
                score += 5.0
            if clean_q:
                if clean_q not in hay:
                    continue
                score += 4.0
            if "alto custo" in str(row.get("pharmacy_type", "")).lower():
                score += 1.0

            row_lat = _optional_float(row.get("latitude"))
            row_lng = _optional_float(row.get("longitude"))
            dist_km: float | None = None
            if lat is not None and lng is not None and row_lat is not None and row_lng is not None:
                dist_km = round(haversine_km(lat, lng, row_lat, row_lng), 2)
                score += max(0.0, 4.0 - dist_km * 0.1)

            scored.append(
                (
                    score,
                    PharmacyLocationDTO(
                        cnes=str(row.get("cnes", "")),
                        name=str(row.get("name", "")),
                        address=str(row.get("address", "")),
                        neighborhood_or_ra=str(row.get("neighborhood_or_ra", "")),
                        pharmacy_type=str(row.get("pharmacy_type", "")),
                        latitude=row_lat,
                        longitude=row_lng,
                        google_maps_url=str(row.get("google_maps_url", "")),
                        covered_ras=covered,
                        distance_km=dist_km,
                    ),
                )
            )

        if not scored:
            return NearbyPharmaciesResponseDTO(
                ra=ra or "Distrito Federal",
                total=0,
                update_schedule=schedule,
                items=[],
            )

        has_gps = lat is not None and lng is not None
        if has_gps:
            scored.sort(
                key=lambda pair: (
                    pair[1].distance_km is None,
                    pair[1].distance_km if pair[1].distance_km is not None else float("inf"),
                    -pair[0],
                    pair[1].name,
                )
            )
        else:
            scored.sort(key=lambda pair: (-pair[0], pair[1].name))
        return NearbyPharmaciesResponseDTO(
            ra=ra or "Distrito Federal",
            total=len(scored),
            update_schedule=schedule,
            items=[item for _, item in scored[:limite]],
        )

    def query_ceaf_stock(
        self,
        *,
        q: str = "",
        unidade: str = "",
        limite: int = 15,
        now_utc: datetime | None = None,
    ) -> CeafStockResponseDTO:
        raw = self._load_stock()
        synced_at_utc = str(raw["synced_at_utc"]) if raw.get("synced_at_utc") is not None else None
        rows: list[dict[str, Any]] = list(raw.get("items", []))
        norm_q = normalizar_texto_pt(q)
        tokens_q = [t for t in norm_q.split() if len(t) > 1]
        norm_u = normalizar_texto_pt(unidade)

        matched: list[CeafStockItemDTO] = []
        for row in rows:
            desc = str(row.get("desc_produto", row.get("medicamento", "")))
            unit = str(row.get("unidade", row.get("farmacia", "")))
            norm_desc = normalizar_texto_pt(desc)
            norm_unit = normalizar_texto_pt(unit)
            if tokens_q and not all(tok in norm_desc for tok in tokens_q):
                continue
            if norm_u and norm_u not in norm_unit:
                continue
            source_date = parse_source_timestamp_utc(row.get("ultima_atualizacao"))
            item_updated_at = source_date.isoformat() if source_date else None
            matched.append(
                CeafStockItemDTO(
                    cod_produto=str(row.get("cod_produto", row.get("cod_produto2", ""))),
                    desc_produto=desc,
                    unidade=unit,
                    disp_estoque=str(row.get("disp_estoque", "")),
                    origem_abastecimento=str(row.get("origem_abastecimento", "")),
                    psicotropico=str(row.get("psicotropico", "")),
                    ultima_atualizacao=str(row.get("ultima_atualizacao") or ""),
                    updated_at=item_updated_at,
                    stale_warning=_is_snapshot_stale(item_updated_at, now_utc=now_utc),
                )
            )

        # Resumo conservador de TODOS os resultados, inclusive além do limite da página.
        dates = [item.updated_at for item in matched if item.updated_at is not None]
        updated_at = min(dates) if matched and len(dates) == len(matched) else None
        stale = not matched or any(item.stale_warning for item in matched)
        return CeafStockResponseDTO(
            query=q,
            unidade=unidade or "Todas",
            updated_at=updated_at,
            synced_at_utc=synced_at_utc,
            stale_warning=stale,
            total=len(matched),
            items=matched[:limite],
        )
