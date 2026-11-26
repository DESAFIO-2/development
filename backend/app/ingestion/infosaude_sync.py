"""Sincronizador público InfoSaúde-DF (CEAF + Estabelecimentos SES-DF) via Power BI DSR.

Portado e adaptado de Data-Science (`infosaude_client.py`) e data-engineering (`infosaude_live.py`)
usando apenas biblioteca padrão Python (`urllib.request`) com validação estrita de HTTPS.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

POWERBI_QUERY_ENDPOINT = (
    "https://wabi-brazil-south-api.analysis.windows.net/public/reports/querydata?synchronous=true"
)

CEAF_RESOURCE_KEY = "a665320c-1f2b-43cd-8380-6d39f535daf9"
CEAF_MODEL_ID = 10730466
CEAF_DATASET_ID = "424ade14-3f72-4830-a4dc-ab612ad877ee"

DOC_MAPS_RESOURCE_KEY = "d77b9ba0-317a-4041-88a0-3241c35384ac"
DOC_MAPS_MODEL_ID = 10722913
DOC_MAPS_DATASET_ID = "c021e607-7580-407e-bbab-4312c5c14cd9"

CEAF_SOURCE_URL = (
    "https://info.saude.df.gov.br/saude-do-cidadao/"
    "painel-infosaude-farmacias-de-alto-custo/estoque-de-medicamentos/"
)
MAPS_SOURCE_URL = "https://info.saude.df.gov.br/como-garantir-seu-medicamento/"

_CEAF_POLOS: tuple[dict[str, Any], ...] = (
    {
        "cnes": "CEAF-ASA-SUL",
        "name": "Farmácia Asa Sul",
        "address": "Estação 102 Sul do Metrô - Subsolo, Asa Sul, Brasília - DF",
        "neighborhood_or_ra": "Plano Piloto (Asa Sul)",
        "pharmacy_type": "Farmácias do Componente Especializado (Alto Custo - CEAF)",
        "latitude": -15.805559821788533,
        "longitude": -47.89002923432857,
        "google_maps_url": (
            "https://www.google.com/maps/search/?api=1&query=-15.805559821788533,-47.89002923432857"
        ),
        "covered_ras": [
            "Asa Norte",
            "Asa Sul",
            "Cruzeiro",
            "Guará",
            "Itapoã",
            "Jardim Botânico",
            "Lago Norte",
            "Lago Sul",
            "Noroeste",
            "Núcleo Bandeirante",
            "Paranoá",
            "Planaltina",
            "São Sebastião",
            "Sobradinho",
            "Sudoeste",
            "Varjão",
        ],
    },
    {
        "cnes": "CEAF-CEILANDIA",
        "name": "Farmácia de Ceilândia",
        "address": "EQNN 18/20 Bloco B, Praça do Cidadão, Ceilândia Sul - DF",
        "neighborhood_or_ra": "Ceilândia",
        "pharmacy_type": "Farmácias do Componente Especializado (Alto Custo - CEAF)",
        "latitude": -15.814780572926943,
        "longitude": -48.10668412457063,
        "google_maps_url": (
            "https://www.google.com/maps/search/?api=1&query=-15.814780572926943,-48.10668412457063"
        ),
        "covered_ras": [
            "Águas Claras",
            "Arniqueira",
            "Brazlândia",
            "Candangolândia",
            "Ceilândia",
            "Estrutural",
            "Park Way",
            "Recanto das Emas",
            "Riacho Fundo I",
            "Riacho Fundo II",
            "Samambaia",
            "Sol Nascente/Pôr do Sol",
            "Taguatinga",
            "Vicente Pires",
        ],
    },
    {
        "cnes": "CEAF-GAMA",
        "name": "Farmácia do Gama",
        "address": "Praça 1, Setor Leste (ao lado da Rodoviária), Gama - DF",
        "neighborhood_or_ra": "Gama",
        "pharmacy_type": "Farmácias do Componente Especializado (Alto Custo - CEAF)",
        "latitude": -16.017253118821127,
        "longitude": -48.06224737829098,
        "google_maps_url": (
            "https://www.google.com/maps/search/?api=1&query=-16.017253118821127,-48.06224737829098"
        ),
        "covered_ras": ["Gama", "Santa Maria"],
    },
)


def decode_powerbi_dsr(ds_block: dict[str, Any]) -> list[list[Any]]:
    """Descomprime o bloco DSR do Power BI aplicando máscaras `R`, `Ø` e `ValueDicts`."""
    ph_list = ds_block.get("PH", [])
    if not ph_list or "DM0" not in ph_list[0]:
        return []
    dm0 = ph_list[0]["DM0"]
    if not dm0:
        return []

    vdicts: dict[str, list[Any]] = ds_block.get("ValueDicts", {})
    schema = dm0[0].get("S", [])
    col_dicts = [col_spec.get("DN") for col_spec in schema]
    n_cols = len(schema)

    prev_row: list[Any] = [None] * n_cols
    decoded: list[list[Any]] = []
    for item in dm0:
        c_vals = item.get("C", [])
        r_mask = int(item.get("R", 0))
        null_mask = int(item.get("Ø", 0))
        row: list[Any] = [None] * n_cols
        c_idx = 0

        for col_i in range(n_cols):
            if (r_mask >> col_i) & 1:
                row[col_i] = prev_row[col_i]
            elif (null_mask >> col_i) & 1:
                row[col_i] = None
            else:
                raw_val = c_vals[c_idx] if c_idx < len(c_vals) else None
                c_idx += 1
                dict_name = col_dicts[col_i]
                if (
                    dict_name
                    and raw_val is not None
                    and isinstance(raw_val, int)
                    and not isinstance(raw_val, bool)
                    and dict_name in vdicts
                    and 0 <= raw_val < len(vdicts[dict_name])
                ):
                    row[col_i] = vdicts[dict_name][raw_val]
                else:
                    row[col_i] = raw_val
        prev_row = row
        decoded.append(row)
    return decoded


def build_ceaf_query_payload() -> dict[str, Any]:
    """Monta a consulta SemanticQueryDataShapeCommand para `estoque_geral_ceaf`."""
    props = (
        "cod_produto2",
        "desc_produto",
        "unidade",
        "disp_estoque",
        "Origem do Abastecimento",
        "Texto Info",
        "psicotropico",
        "ultima_atualizacao",
    )
    return {
        "version": "1.0.0",
        "queries": [
            {
                "Query": {
                    "Commands": [
                        {
                            "SemanticQueryDataShapeCommand": {
                                "Query": {
                                    "Version": 2,
                                    "From": [
                                        {"Name": "e", "Entity": "estoque_geral_ceaf", "Type": 0}
                                    ],
                                    "Select": [
                                        {
                                            "Column": {
                                                "Expression": {"SourceRef": {"Source": "e"}},
                                                "Property": prop,
                                            },
                                            "Name": f"e.{prop}",
                                        }
                                        for prop in props
                                    ],
                                },
                                "Binding": {
                                    "Primary": {
                                        "Groupings": [{"Projections": list(range(len(props)))}]
                                    },
                                    "DataReduction": {
                                        "DataVolume": 6,
                                        "Primary": {"Window": {"Count": 30000}},
                                    },
                                    "Version": 1,
                                },
                                "ExecutionMetricsKind": 1,
                            }
                        }
                    ]
                },
                "QueryId": "query_stock_ceaf_clean",
                "ApplicationContext": {"DatasetId": CEAF_DATASET_ID},
            }
        ],
        "cancelQueries": [],
        "modelId": CEAF_MODEL_ID,
    }


def build_establishments_query_payload() -> dict[str, Any]:
    """Monta a consulta Power BI para a tabela `Estabelecimentos`."""
    props = (
        "cnes",
        "nome_fanta",
        "logradouro",
        "numero",
        "complement",
        "bairro",
        "latitude",
        "longitude",
        "tipo_farmacia",
    )
    return {
        "version": "1.0.0",
        "queries": [
            {
                "Query": {
                    "Commands": [
                        {
                            "SemanticQueryDataShapeCommand": {
                                "Query": {
                                    "Version": 2,
                                    "From": [
                                        {"Name": "e", "Entity": "Estabelecimentos", "Type": 0}
                                    ],
                                    "Select": [
                                        {
                                            "Column": {
                                                "Expression": {"SourceRef": {"Source": "e"}},
                                                "Property": prop,
                                            },
                                            "Name": f"e.{prop}",
                                        }
                                        for prop in props
                                    ],
                                },
                                "Binding": {
                                    "Primary": {
                                        "Groupings": [{"Projections": list(range(len(props)))}]
                                    },
                                    "DataReduction": {
                                        "DataVolume": 3,
                                        "Primary": {"Window": {"Count": 1000}},
                                    },
                                    "Version": 1,
                                },
                            }
                        }
                    ]
                },
                "QueryId": "",
                "ApplicationContext": {
                    "DatasetId": DOC_MAPS_DATASET_ID,
                    "Sources": [{"ReportId": DOC_MAPS_RESOURCE_KEY}],
                },
            }
        ],
        "cancelQueries": [],
        "modelId": DOC_MAPS_MODEL_ID,
    }


def post_powerbi_query(
    resource_key: str,
    payload: dict[str, Any],
    *,
    endpoint: str = POWERBI_QUERY_ENDPOINT,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Executa POST em endpoint HTTPS do Power BI validando o esquema antes da chamada."""
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme != "https":
        raise ValueError(f"Endpoint InfoSaúde exige HTTPS: {endpoint!r}")
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-PowerBI-ResourceKey": resource_key,
            "User-Agent": "SUSCidadao-Backend/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
        body: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
        return body


def parse_ceaf_stock_payload(
    raw_stock: dict[str, Any], *, synced_at_utc: str | None = None
) -> dict[str, Any]:
    """Converte resposta DSR do CEAF no contrato consumido por `LocalPharmacyStockRepository`."""
    ds_stock = raw_stock["results"][0]["result"]["data"]["dsr"]["DS"][0]
    rows = decode_powerbi_dsr(ds_stock)
    if not rows:
        raise ValueError("Painel CEAF retornou conjunto vazio.")

    items: list[dict[str, str]] = []
    last_update = ""
    for row in rows:
        updated = str(row[7] or last_update)
        if row[7]:
            last_update = updated
        items.append(
            {
                "cod_produto": str(row[0] or ""),
                "desc_produto": str(row[1] or ""),
                "unidade": str(row[2] or ""),
                "disp_estoque": str(row[3] or "SEM INFORMAÇÃO"),
                "origem_abastecimento": str(row[4] or "SES-DF"),
                "psicotropico": str(row[6] or "Outros"),
                "ultima_atualizacao": updated,
            }
        )

    by_status = dict(Counter(i["disp_estoque"] for i in items))
    by_unit = {
        unit: dict(Counter(i["disp_estoque"] for i in items if i["unidade"] == unit))
        for unit in ("Asa Sul", "Ceilândia", "Gama")
    }
    return {
        "source_url": CEAF_SOURCE_URL,
        "powerbi_api_endpoint": POWERBI_QUERY_ENDPOINT,
        "resource_key": CEAF_RESOURCE_KEY,
        "panel_updated_at_utc": synced_at_utc or datetime.now(UTC).isoformat(),
        "update_schedule": "Diária (00:00 BRT e atualização intradiária ~13:45-14:37 BRT)",
        "total_records": len(items),
        "distinct_medications": len({i["desc_produto"] for i in items if i["desc_produto"]}),
        "stock_by_status": by_status,
        "stock_by_unit": by_unit,
        "items": items,
    }


def parse_establishments_payload(raw_estab: dict[str, Any]) -> dict[str, Any]:
    """Converte resposta DSR de `Estabelecimentos` mantendo as 3 unidades CEAF-DF."""
    ds_estab = raw_estab["results"][0]["result"]["data"]["dsr"]["DS"][0]
    rows = decode_powerbi_dsr(ds_estab)
    if not rows:
        raise ValueError("Painel de estabelecimentos retornou conjunto vazio.")

    pharmacies: list[dict[str, Any]] = [dict(p) for p in _CEAF_POLOS]
    geolocated_count = len(_CEAF_POLOS)
    for row in rows:
        cnes = str(row[0] or "")
        name = str(row[1] or "")
        logradouro = str(row[2] or "")
        numero = str(row[3] or "")
        complemento = str(row[4] or "")
        bairro = str(row[5] or "")
        lat = float(row[6]) if row[6] is not None else None
        lng = float(row[7]) if row[7] is not None else None
        ptype = str(row[8] or "")
        address = ", ".join(part for part in (logradouro, numero, complemento) if part).strip()
        if lat is not None and lng is not None:
            geolocated_count += 1
            maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
        else:
            maps_url = f"https://www.google.com/maps/search/?api=1&query={name}+{bairro}+DF"
        pharmacies.append(
            {
                "cnes": cnes,
                "name": name,
                "address": address or bairro,
                "neighborhood_or_ra": bairro,
                "pharmacy_type": ptype,
                "latitude": lat,
                "longitude": lng,
                "google_maps_url": maps_url,
            }
        )

    return {
        "source_url": MAPS_SOURCE_URL,
        "powerbi_api_endpoint": POWERBI_QUERY_ENDPOINT,
        "ceaf_resource_key": CEAF_RESOURCE_KEY,
        "establishments_resource_key": DOC_MAPS_RESOURCE_KEY,
        "update_schedule": "Semanal (Segundas-feiras às 00:19 BRT)",
        "total_establishments": len(pharmacies),
        "geolocated_with_lat_lng": geolocated_count,
        "pharmacies": pharmacies,
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=".sync-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def sync_infosaude_files(
    output_dir: Path,
    *,
    sync_maps: bool = True,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Sincroniza estoque CEAF e (opcionalmente) estabelecimentos para `output_dir`."""
    raw_stock = post_powerbi_query(CEAF_RESOURCE_KEY, build_ceaf_query_payload(), timeout=timeout)
    stock_out = parse_ceaf_stock_payload(raw_stock)
    _atomic_write_json(output_dir / "ceaf_live_stock.json", stock_out)

    maps_total: int | None = None
    if sync_maps:
        raw_estab = post_powerbi_query(
            DOC_MAPS_RESOURCE_KEY, build_establishments_query_payload(), timeout=timeout
        )
        maps_out = parse_establishments_payload(raw_estab)
        _atomic_write_json(output_dir / "df_pharmacies_geolocated.json", maps_out)
        maps_total = int(maps_out["total_establishments"])

    return {
        "panel_updated_at_utc": stock_out["panel_updated_at_utc"],
        "stock_records": stock_out["total_records"],
        "distinct_medications": stock_out["distinct_medications"],
        "total_establishments": maps_total,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="Diretório de saída dos snapshots (padrão: data/processed)",
    )
    parser.add_argument(
        "--no-maps",
        action="store_true",
        help="Atualiza somente ceaf_live_stock.json sem consultar Estabelecimentos",
    )
    args = parser.parse_args()
    summary = sync_infosaude_files(args.output_dir, sync_maps=not args.no_maps)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
