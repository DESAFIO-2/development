"""Testes de repositório e API para farmácias geolocalizadas e estoque CEAF-DF."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.infrastructure.persistence.repositories.pharmacy_stock_repository import (
    LocalPharmacyStockRepository,
)
from app.main import app


def _seed_files(base_dir: Path, *, updated_at: str | None, synced_at: str | None = None) -> None:
    maps_payload = {
        "update_schedule": "Semanal",
        "pharmacies": [
            {
                "cnes": "CEAF-ASA-SUL",
                "name": "Farmácia Asa Sul",
                "address": "102 Sul",
                "neighborhood_or_ra": "Asa Sul",
                "pharmacy_type": "Farmácias do Componente Especializado (Alto Custo - CEAF)",
                "latitude": -15.8055,
                "longitude": -47.8900,
                "google_maps_url": "https://maps.google.com/?q=-15.8055,-47.89",
                "covered_ras": ["Asa Sul", "Guará"],
            },
            {
                "cnes": "CEAF-CEILANDIA",
                "name": "Farmácia de Ceilândia",
                "address": "EQNN 18/20",
                "neighborhood_or_ra": "Ceilândia",
                "pharmacy_type": "Farmácias do Componente Especializado (Alto Custo - CEAF)",
                "latitude": -15.8147,
                "longitude": -48.1066,
                "google_maps_url": "https://maps.google.com/?q=-15.8147,-48.1066",
                "covered_ras": ["Ceilândia", "Taguatinga"],
            },
            {
                "cnes": "UBS-TAGUATINGA-PERTO",
                "name": "UBS 1 Taguatinga",
                "address": "QNB 10",
                "neighborhood_or_ra": "Taguatinga",
                "pharmacy_type": "Farmácias das Unidades Básicas de Saúde (UBS)",
                "latitude": -15.8330,
                "longitude": -48.0560,
                "google_maps_url": "https://maps.google.com/?q=-15.833,-48.056",
            },
        ],
    }
    stock_payload = {
        "panel_updated_at_utc": updated_at,
        "synced_at_utc": synced_at,
        "items": [
            {
                "cod_produto": "101",
                "desc_produto": "ADALIMUMABE 40 MG SERINGA",
                "unidade": "Ceilândia",
                "disp_estoque": "COM ESTOQUE",
                "origem_abastecimento": "Ministério da Saúde",
                "psicotropico": "Não",
                "ultima_atualizacao": updated_at,
            },
            {
                "cod_produto": "102",
                "desc_produto": "LOSARTANA 50 MG",
                "unidade": "Asa Sul",
                "disp_estoque": "SEM ESTOQUE",
                "origem_abastecimento": "SES-DF",
                "psicotropico": "Não",
                "ultima_atualizacao": updated_at,
            },
        ],
    }
    (base_dir / "df_pharmacies_geolocated.json").write_text(
        json.dumps(maps_payload, ensure_ascii=False), encoding="utf-8"
    )
    (base_dir / "ceaf_live_stock.json").write_text(
        json.dumps(stock_payload, ensure_ascii=False), encoding="utf-8"
    )


def test_repository_filtra_por_ra_gps_e_calcula_frescor(tmp_path: Path) -> None:
    now = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)
    fresh_ts = (now - timedelta(hours=12)).isoformat()
    _seed_files(tmp_path, updated_at=fresh_ts)
    repo = LocalPharmacyStockRepository(data_dir=tmp_path)

    nearby = repo.find_nearby(ra="Taguatinga", lat=-15.815, lng=-48.107, limite=5)
    assert nearby.total == 2
    assert nearby.items[0].cnes == "CEAF-CEILANDIA"
    assert nearby.items[0].distance_km is not None
    assert nearby.items[0].distance_km < 1.0

    # Em busca por GPS ("Próximas"), a UBS mais próxima deve vir antes de um CEAF distante.
    gps_near_ubs = repo.find_nearby(lat=-15.8331, lng=-48.0561, limite=5)
    assert gps_near_ubs.items[0].cnes == "UBS-TAGUATINGA-PERTO"
    assert gps_near_ubs.items[0].distance_km is not None
    assert gps_near_ubs.items[1].distance_km is not None
    assert gps_near_ubs.items[0].distance_km < gps_near_ubs.items[1].distance_km

    gps_only = repo.find_nearby(lat=-15.815, lng=-48.107, limite=5)
    assert gps_only.total == 3
    assert gps_only.items[0].cnes == "CEAF-CEILANDIA"
    assert gps_only.items[1].cnes == "UBS-TAGUATINGA-PERTO"
    assert gps_only.items[2].cnes == "CEAF-ASA-SUL"

    fresh_stock = repo.query_ceaf_stock(q="adalimumabe", unidade="ceilandia", now_utc=now)
    assert fresh_stock.total == 1
    assert fresh_stock.stale_warning is False
    assert fresh_stock.cobertura_escopo == "CEAF_ALTO_CUSTO"
    assert fresh_stock.cobertura_ubs_disponivel is False

    # Coleta recente NÃO pode esconder fonte antiga (ex.: painel de 2020 coletado em 2026).
    _seed_files(
        tmp_path,
        updated_at="2020-01-01T13:00:00+00:00",
        synced_at=now.isoformat(),
    )
    old_source_repo = LocalPharmacyStockRepository(data_dir=tmp_path)
    old_source_stock = old_source_repo.query_ceaf_stock(q="adalimumabe", now_utc=now)
    assert old_source_stock.stale_warning is True
    assert old_source_stock.updated_at == "2020-01-01T13:00:00+00:00"
    assert old_source_stock.synced_at_utc == now.isoformat()

    stale_ts = (now - timedelta(hours=49)).isoformat()
    _seed_files(tmp_path, updated_at=stale_ts)
    stale_repo = LocalPharmacyStockRepository(data_dir=tmp_path)
    stale_stock = stale_repo.query_ceaf_stock(q="adalimumabe", now_utc=now)
    assert stale_stock.stale_warning is True


def test_repository_ausente_nao_falha(tmp_path: Path) -> None:
    repo = LocalPharmacyStockRepository(data_dir=tmp_path)
    assert repo.find_nearby(ra="Ceilândia").total == 0
    stock = repo.query_ceaf_stock(q="adalimumabe")
    assert stock.total == 0
    assert stock.stale_warning is True
    assert stock.cobertura_ubs_disponivel is False


def test_rotas_http_pharmacies_e_ceaf_stock() -> None:
    with TestClient(app) as client:
        pharm = client.get("/api/v1/pharmacies/nearby", params={"ra": "Ceilândia", "limite": 5})
        assert pharm.status_code == 200
        pharm_data = pharm.json()
        assert pharm_data["total"] >= 1
        assert any(it["cnes"] == "CEAF-CEILANDIA" for it in pharm_data["items"])

        bad_gps = client.get("/api/v1/pharmacies/nearby", params={"lat": -15.8})
        assert bad_gps.status_code == 422

        out_of_range = client.get("/api/v1/pharmacies/nearby", params={"lat": 95.0, "lng": -48.0})
        assert out_of_range.status_code == 422

        nan_gps = client.get("/api/v1/pharmacies/nearby", params={"lat": "nan", "lng": -48.0})
        assert nan_gps.status_code == 422

        stock = client.get(
            "/api/v1/ceaf-stock", params={"q": "adalimumabe", "unidade": "Ceilândia"}
        )
        assert stock.status_code == 200
        stock_data = stock.json()
        assert stock_data["cobertura_escopo"] == "CEAF_ALTO_CUSTO"
        assert stock_data["cobertura_ubs_disponivel"] is False
        assert stock_data["total"] >= 1
        assert stock_data["updated_at"] is not None
        assert stock_data["synced_at_utc"] is not None

        cpf = "123.456.789-00"
        pharm_pii = client.get("/api/v1/pharmacies/nearby", params={"ra": f"Ceilândia {cpf}"})
        assert pharm_pii.status_code == 200
        assert cpf not in pharm_pii.text
        assert "[CPF_MASCARADO_LGPD]" in pharm_pii.json()["ra"]

        stock_pii = client.get(
            "/api/v1/ceaf-stock",
            params={"q": f"adalimumabe {cpf}", "unidade": f"CPF {cpf}"},
        )
        assert stock_pii.status_code == 200
        assert cpf not in stock_pii.text
        assert "[CPF_MASCARADO_LGPD]" in stock_pii.json()["query"]
        assert "[CPF_MASCARADO_LGPD]" in stock_pii.json()["unidade"]


def test_frescor_por_item_nao_herda_data_recente_do_painel(tmp_path: Path) -> None:
    now = datetime(2026, 11, 26, 12, tzinfo=UTC)
    _seed_files(tmp_path, updated_at=now.isoformat(), synced_at=now.isoformat())
    path = tmp_path / "ceaf_live_stock.json"
    raw = json.loads(path.read_text())
    raw["items"][1]["ultima_atualizacao"] = "05/11/2026 13:45:15"
    path.write_text(json.dumps(raw))
    repo = LocalPharmacyStockRepository(tmp_path)
    old = repo.query_ceaf_stock(q="losartana", now_utc=now)
    assert old.updated_at == "2026-11-05T16:45:15+00:00"
    assert old.stale_warning and old.items[0].stale_warning
    fresh = repo.query_ceaf_stock(q="adalimumabe", now_utc=now)
    assert not fresh.stale_warning
    assert fresh.items[0].updated_at == now.isoformat()
    # O limite da página não pode esconder a existência de resultados antigos.
    mixed = repo.query_ceaf_stock(limite=1, now_utc=now)
    assert mixed.total == 2 and len(mixed.items) == 1
    assert mixed.stale_warning and mixed.updated_at == old.updated_at
    empty = repo.query_ceaf_stock(q="inexistente", now_utc=now)
    assert empty.updated_at is None and empty.stale_warning


def test_data_desconhecida_ou_futura_nunca_confirma_frescor(tmp_path: Path) -> None:
    now = datetime(2026, 11, 26, 12, tzinfo=UTC)
    for value in (None, "", "inválida", "2099-01-01T00:00:00Z"):
        _seed_files(tmp_path, updated_at=now.isoformat())
        path = tmp_path / "ceaf_live_stock.json"
        raw = json.loads(path.read_text())
        raw["items"][0]["ultima_atualizacao"] = value
        path.write_text(json.dumps(raw))
        result = LocalPharmacyStockRepository(tmp_path).query_ceaf_stock(now_utc=now)
        assert result.stale_warning
        assert result.items[0].stale_warning
        if value != "2099-01-01T00:00:00Z":
            assert result.updated_at is None
            assert result.items[0].updated_at is None
