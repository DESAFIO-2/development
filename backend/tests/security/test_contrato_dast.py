"""Regressão dos achados do DAST (ZAP + Schemathesis), ver docs/security/dast.md.

Cada teste trava um achado já corrigido, para ele não voltar sem que o CI
acuse antes mesmo do job `dast`.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.middleware import CABECALHOS_SEGURANCA
from app.api.schemas.prescription_request import PADRAO_DOIS_VISIVEIS, PADRAO_UM_VISIVEL
from app.main import app

AUDIT = "/api/v1/prescriptions/audit"
ORCHESTRATE = "/api/v1/agents/orchestrate"
MULTIMODAL = "/api/v1/agents/multimodal"
ITEM = {"nome_digitado": "losartana potássica 50 mg"}


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as cliente:
        yield cliente


# --- ZAP: cabeçalhos de segurança -------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "rota", "kwargs", "status"),
    [
        ("get", "/health", {}, 200),
        ("post", AUDIT, {"json": {}}, 422),
        ("get", "/nao-existe", {}, 404),
    ],
)
def test_cabecalhos_de_seguranca_em_sucesso_e_erro(
    client: TestClient, metodo: str, rota: str, kwargs: dict[str, Any], status: int
) -> None:
    resposta = getattr(client, metodo)(rota, **kwargs)
    assert resposta.status_code == status
    for nome, valor in CABECALHOS_SEGURANCA.items():
        assert resposta.headers[nome] == valor


# --- Schemathesis ST103: códigos documentados -------------------------------


def test_openapi_documenta_os_codigos_de_erro() -> None:
    caminhos = app.openapi()["paths"]
    assert {"200", "400", "422"} <= set(caminhos[AUDIT]["post"]["responses"])
    assert {"200", "400", "422"} <= set(caminhos[ORCHESTRATE]["post"]["responses"])
    assert {"200", "400", "413", "415", "422"} <= set(caminhos[MULTIMODAL]["post"]["responses"])


def test_json_malformado_devolve_400_documentado(client: TestClient) -> None:
    resposta = client.post(AUDIT, content=b"\xff", headers={"Content-Type": "application/json"})
    assert resposta.status_code == 400
    assert isinstance(resposta.json()["detail"], str)


# --- Schemathesis ST201: data estrita ---------------------------------------


@pytest.mark.parametrize("rota", [AUDIT, ORCHESTRATE])
@pytest.mark.parametrize("data", [0, 1700000000, "1700000000", "2026-1-5", "05/01/2026", True])
def test_data_emissao_so_aceita_aaaa_mm_dd(client: TestClient, rota: str, data: object) -> None:
    resposta = client.post(rota, json={"itens": [ITEM], "data_emissao": data})
    assert resposta.status_code == 422
    assert ("body", "data_emissao") in {tuple(e["loc"]) for e in resposta.json()["detail"]}


def test_data_emissao_iso_continua_aceita(client: TestClient) -> None:
    resposta = client.post(AUDIT, json={"itens": [ITEM], "data_emissao": "2026-01-05"})
    assert resposta.status_code == 200


# --- Schemathesis ST202: contrato igual à validação -------------------------


def test_classe_visivel_e_exatamente_o_complemento_de_isspace() -> None:
    espacos = [chr(c) for c in range(sys.maxunicode + 1) if chr(c).isspace()]
    assert all(re.fullmatch(PADRAO_UM_VISIVEL, c) is None for c in espacos)
    for visivel in ("a", "0", "﻿", "​", "ç"):
        assert re.fullmatch(PADRAO_UM_VISIVEL, visivel)


def test_openapi_publica_as_mesmas_regras_da_validacao() -> None:
    schemas = app.openapi()["components"]["schemas"]
    nome = schemas["MedicationItemDTO"]["properties"]["nome_digitado"]
    assert nome["pattern"] == PADRAO_DOIS_VISIVEIS
    ramos = schemas["AgentRequestDTO"]["anyOf"]
    assert {"required": ["itens"], "properties": {"itens": {"minItems": 1}}} in ramos
    pergunta = next(r for r in ramos if r["required"] == ["pergunta_adicional"])
    assert pergunta["properties"]["pergunta_adicional"]["pattern"] == PADRAO_UM_VISIVEL


@pytest.mark.parametrize("nome", ["0\r", "0\x1f", "\x1ca", " a "])
def test_nome_precisa_de_dois_caracteres_visiveis(client: TestClient, nome: str) -> None:
    resposta = client.post(AUDIT, json={"itens": [{"nome_digitado": nome}]})
    assert resposta.status_code == 422


def test_nome_com_controle_entre_visiveis_e_aceito(client: TestClient) -> None:
    resposta = client.post(AUDIT, json={"itens": [{"nome_digitado": "\x1closartana"}]})
    assert resposta.status_code == 200


@pytest.mark.parametrize("pergunta", ["\x1f", "　", "\x85 "])
def test_orchestrate_rejeita_pergunta_so_com_espacos(client: TestClient, pergunta: str) -> None:
    resposta = client.post(ORCHESTRATE, json={"pergunta_adicional": pergunta})
    assert resposta.status_code == 422


# --- Multimodal: entradas permissivas que passavam --------------------------


@pytest.mark.parametrize("valor", ["0", "1", "yes", "on", "True", "FALSE", ""])
def test_multimodal_confirmacao_so_aceita_true_ou_false(client: TestClient, valor: str) -> None:
    resposta = client.post(
        MULTIMODAL,
        data={"pergunta_adicional": "Onde retiro losartana?", "confirmado_pelo_usuario": valor},
    )
    assert resposta.status_code == 422


@pytest.mark.parametrize("valor", ["true", "false"])
def test_multimodal_confirmacao_true_false_continua_aceita(client: TestClient, valor: str) -> None:
    resposta = client.post(
        MULTIMODAL,
        data={"pergunta_adicional": "Onde retiro losartana?", "confirmado_pelo_usuario": valor},
    )
    assert resposta.status_code == 200


@pytest.mark.parametrize(
    ("data", "status"), [("", 200), (" ", 422), ("0", 422), ("2026-01-05", 200)]
)
def test_multimodal_data_vazia_e_nao_informada_e_espaco_e_erro(
    client: TestClient, data: str, status: int
) -> None:
    resposta = client.post(
        MULTIMODAL, data={"pergunta_adicional": "Onde retiro losartana?", "data_emissao": data}
    )
    assert resposta.status_code == status


@pytest.mark.parametrize("campo", ["pdf_file", "audio_file"])
def test_multimodal_arquivo_enviado_como_texto_e_rejeitado(client: TestClient, campo: str) -> None:
    resposta = client.post(MULTIMODAL, data={campo: "não sou um arquivo"})
    assert resposta.status_code == 422
    assert campo in resposta.json()["detail"]


def test_cors_e_corp_preservam_same_origin_por_padrao_e_liberam_expo_autorizado(
    client: TestClient,
) -> None:
    allowed = "http://localhost:8081"
    preflight = client.options(
        "/api/v1/agents/orchestrate",
        headers={
            "Origin": allowed,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Origin"] == allowed
    assert preflight.headers["Cross-Origin-Resource-Policy"] == "cross-origin"
    assert preflight.headers["X-Content-Type-Options"] == "nosniff"

    resp_ok = client.get("/health", headers={"Origin": allowed})
    assert resp_ok.status_code == 200
    assert resp_ok.headers["Access-Control-Allow-Origin"] == allowed
    assert resp_ok.headers["Cross-Origin-Resource-Policy"] == "cross-origin"

    resp_untrusted = client.get("/health", headers={"Origin": "https://site-terceiro.invalid"})
    assert resp_untrusted.status_code == 200
    assert "Access-Control-Allow-Origin" not in resp_untrusted.headers
    assert resp_untrusted.headers["Cross-Origin-Resource-Policy"] == "same-origin"
