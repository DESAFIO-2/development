"""Testes unitários offline para o sincronizador InfoSaúde-DF (Power BI DSR)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.ingestion.infosaude_sync import (
    decode_powerbi_dsr,
    parse_ceaf_stock_payload,
    parse_establishments_payload,
    post_powerbi_query,
    sync_infosaude_files,
)


def _sample_ceaf_dsr() -> dict[str, object]:
    return {
        "results": [
            {
                "result": {
                    "data": {
                        "dsr": {
                            "DS": [
                                {
                                    "ValueDicts": {
                                        "D0": ["90001"],
                                        "D1": ["ADALIMUMABE 40 MG"],
                                        "D2": ["Ceilândia", "Asa Sul"],
                                        "D3": ["COM ESTOQUE", "SEM ESTOQUE"],
                                        "D4": ["Ministério da Saúde"],
                                        "D5": ["Não"],
                                        "D6": ["26/11/2026 09:00:00"],
                                    },
                                    "PH": [
                                        {
                                            "DM0": [
                                                {
                                                    "S": [
                                                        {"DN": "D0"},
                                                        {"DN": "D1"},
                                                        {"DN": "D2"},
                                                        {"DN": "D3"},
                                                        {"DN": "D4"},
                                                        {},
                                                        {"DN": "D5"},
                                                        {"DN": "D6"},
                                                    ],
                                                    "C": [0, 0, 0, 0, 0, "Info", 0, 0],
                                                },
                                                {
                                                    "R": 1 + 2 + 16 + 32 + 64 + 128,
                                                    "C": [1, 1],
                                                },
                                            ]
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                }
            }
        ]
    }


def _sample_establishments_dsr() -> dict[str, object]:
    return {
        "results": [
            {
                "result": {
                    "data": {
                        "dsr": {
                            "DS": [
                                {
                                    "ValueDicts": {"D0": ["12345"], "D1": ["UBS 1 CEILANDIA"]},
                                    "PH": [
                                        {
                                            "DM0": [
                                                {
                                                    "S": [
                                                        {"DN": "D0"},
                                                        {"DN": "D1"},
                                                        {},
                                                        {},
                                                        {},
                                                        {},
                                                        {},
                                                        {},
                                                        {},
                                                    ],
                                                    "C": [
                                                        0,
                                                        0,
                                                        "QNN 1",
                                                        "10",
                                                        None,
                                                        "Ceilândia",
                                                        -15.82,
                                                        -48.11,
                                                        "UBS",
                                                    ],
                                                    "Ø": 0,
                                                }
                                            ]
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                }
            }
        ]
    }


def test_decode_powerbi_dsr_e_parsers() -> None:
    raw_stock = _sample_ceaf_dsr()
    ds = raw_stock["results"][0]["result"]["data"]["dsr"]["DS"][0]  # type: ignore[index]
    rows = decode_powerbi_dsr(ds)
    assert len(rows) == 2
    assert rows[1][0] == "90001"
    assert rows[1][2] == "Asa Sul"
    assert rows[1][3] == "SEM ESTOQUE"

    stock_out = parse_ceaf_stock_payload(raw_stock, synced_at_utc="2026-11-26T12:00:00+00:00")
    assert stock_out["total_records"] == 2
    assert stock_out["distinct_medications"] == 1
    assert stock_out["stock_by_unit"]["Ceilândia"]["COM ESTOQUE"] == 1
    assert stock_out["panel_updated_at_utc"] == "2026-11-26T12:00:00+00:00"
    assert stock_out["synced_at_utc"] == "2026-11-26T12:00:00+00:00"

    maps_out = parse_establishments_payload(_sample_establishments_dsr())
    assert maps_out["total_establishments"] == 4
    assert maps_out["geolocated_with_lat_lng"] == 4


def test_parse_ceaf_separa_data_fonte_da_data_de_coleta() -> None:
    stale_source = _sample_ceaf_dsr()
    stale_source["results"][0]["result"]["data"]["dsr"]["DS"][0]["ValueDicts"]["D6"] = [  # type: ignore[index]
        "01/01/2020 10:00:00"
    ]
    parsed = parse_ceaf_stock_payload(stale_source, synced_at_utc="2026-11-26T18:00:00+00:00")
    assert parsed["synced_at_utc"] == "2026-11-26T18:00:00+00:00"
    assert parsed["panel_updated_at_utc"] == "2020-01-01T13:00:00+00:00"

    missing_date = _sample_ceaf_dsr()
    missing_date["results"][0]["result"]["data"]["dsr"]["DS"][0]["ValueDicts"]["D6"] = [""]  # type: ignore[index]
    parsed_missing = parse_ceaf_stock_payload(
        missing_date, synced_at_utc="2026-11-26T18:00:00+00:00"
    )
    assert parsed_missing["synced_at_utc"] == "2026-11-26T18:00:00+00:00"
    assert parsed_missing["panel_updated_at_utc"] is None


def test_post_powerbi_query_rejeita_http_nao_seguro() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        post_powerbi_query("k", {}, endpoint="http://insecure.local/query")


def test_sync_infosaude_files_grava_snapshots_atomicos(tmp_path: Path) -> None:
    with patch(
        "app.ingestion.infosaude_sync.post_powerbi_query",
        side_effect=[_sample_ceaf_dsr(), _sample_establishments_dsr()],
    ):
        summary = sync_infosaude_files(tmp_path)
    assert summary["stock_records"] == 2
    assert summary["total_establishments"] == 4
    stock_json = json.loads((tmp_path / "ceaf_live_stock.json").read_text(encoding="utf-8"))
    maps_json = json.loads((tmp_path / "df_pharmacies_geolocated.json").read_text(encoding="utf-8"))
    assert len(stock_json["items"]) == 2
    assert len(maps_json["pharmacies"]) == 4


def test_data_nula_dsr_nao_herda_data_da_linha_anterior() -> None:
    raw = _sample_ceaf_dsr()
    ds = raw["results"][0]["result"]["data"]["dsr"]["DS"][0]  # type: ignore[index]
    second = ds["PH"][0]["DM0"][1]
    second["R"] &= ~128
    second["Ø"] = 128
    assert decode_powerbi_dsr(ds)[1][7] is None
    parsed = parse_ceaf_stock_payload(raw)
    assert parsed["items"][0]["ultima_atualizacao"] == "26/11/2026 09:00:00"
    assert parsed["items"][1]["ultima_atualizacao"] == ""
