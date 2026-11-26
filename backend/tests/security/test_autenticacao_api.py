"""Autenticação ponta a ponta pela API: rotas /auth, rotas protegidas e subida em produção."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import autenticacao as mod_auth
from app.main import app

CPF = "529.982.247-25"
CPF_SEM_CONTA = "168.995.350-09"
SENHA = "girassol-azul-42"
AUDIT = "/api/v1/prescriptions/audit"
ITEM = {"itens": [{"nome_digitado": "losartana potássica 50 mg"}]}
PASTA_BACKEND = Path(__file__).resolve().parents[2]

ROTAS_PROTEGIDAS = [
    ("post", AUDIT, {"json": ITEM}),
    ("post", "/api/v1/agents/orchestrate", {"json": ITEM}),
    ("post", "/api/v1/agents/multimodal", {"data": {"pergunta_adicional": "Onde retiro?"}}),
    ("get", "/api/v1/pharmacies/nearby", {"params": {"ra": "Asa Sul"}}),
    ("get", "/api/v1/ceaf-stock", {}),
]


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Um client por teste: o lifespan cria um repositório em memória novo a cada vez.
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def exigir_login(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Depende do client: o lifespan dele reconfigura a exigência ao subir.
    monkeypatch.setattr(mod_auth, "_exigida", True)


def _cadastrar(client: TestClient) -> dict[str, str]:
    r = client.post("/api/v1/auth/cadastro", json={"cpf": CPF, "senha": SENHA})
    assert r.status_code == 201, r.text
    tokens: dict[str, str] = r.json()
    return tokens


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Fluxo completo -------------------------------------------------------------


def test_cadastro_login_refresh_eu_e_sair(client: TestClient) -> None:
    cadastro = _cadastrar(client)
    assert set(cadastro) == {"access_token", "refresh_token", "token_type", "expires_in"}
    assert "52998224725" not in str(cadastro)

    login = client.post("/api/v1/auth/login", json={"cpf": "52998224725", "senha": SENHA})
    assert login.status_code == 200

    eu = client.get("/api/v1/auth/eu", headers=_bearer(login.json()["access_token"]))
    assert eu.status_code == 200 and "id" in eu.json()

    novo = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]}
    )
    assert novo.status_code == 200
    assert novo.json()["refresh_token"] != login.json()["refresh_token"]

    sair = client.post("/api/v1/auth/sair", json={"refresh_token": novo.json()["refresh_token"]})
    assert sair.status_code == 204
    depois = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": novo.json()["refresh_token"]}
    )
    assert depois.status_code == 401


def test_cadastro_duplicado_409(client: TestClient) -> None:
    _cadastrar(client)
    r = client.post("/api/v1/auth/cadastro", json={"cpf": CPF, "senha": "outra-senha-boa"})
    assert r.status_code == 409


@pytest.mark.parametrize(
    ("cpf", "senha"), [("111.111.111-11", SENHA), (CPF, "12345678"), (CPF, "curta")]
)
def test_cadastro_com_cpf_ou_senha_invalidos_422(client: TestClient, cpf: str, senha: str) -> None:
    r = client.post("/api/v1/auth/cadastro", json={"cpf": cpf, "senha": senha})
    assert r.status_code == 422


def test_campos_extras_sao_recusados(client: TestClient) -> None:
    r = client.post("/api/v1/auth/cadastro", json={"cpf": CPF, "senha": SENHA, "admin": True})
    assert r.status_code == 422


def test_login_nao_diz_se_o_cpf_existe(client: TestClient) -> None:
    _cadastrar(client)
    senha_errada = client.post("/api/v1/auth/login", json={"cpf": CPF, "senha": "errada-123!"})
    sem_conta = client.post("/api/v1/auth/login", json={"cpf": CPF_SEM_CONTA, "senha": SENHA})
    assert senha_errada.status_code == sem_conta.status_code == 401
    assert senha_errada.json() == sem_conta.json()
    assert senha_errada.headers["WWW-Authenticate"] == "Bearer"


def test_eu_sem_token_401(client: TestClient) -> None:
    assert client.get("/api/v1/auth/eu").status_code == 401


# --- Rotas protegidas -------------------------------------------------------------


@pytest.mark.parametrize(("metodo", "rota", "kwargs"), ROTAS_PROTEGIDAS)
def test_local_sem_token_passa_como_anonimo(
    client: TestClient, metodo: str, rota: str, kwargs: dict[str, object]
) -> None:
    assert getattr(client, metodo)(rota, **kwargs).status_code == 200


@pytest.mark.parametrize(("metodo", "rota", "kwargs"), ROTAS_PROTEGIDAS)
def test_token_invalido_e_401_mesmo_no_local(
    client: TestClient, metodo: str, rota: str, kwargs: dict[str, object]
) -> None:
    r = getattr(client, metodo)(rota, headers=_bearer("nao.e.token"), **kwargs)
    assert r.status_code == 401


@pytest.mark.usefixtures("exigir_login")
@pytest.mark.parametrize(("metodo", "rota", "kwargs"), ROTAS_PROTEGIDAS)
def test_login_exigido_sem_token_401(
    client: TestClient, metodo: str, rota: str, kwargs: dict[str, object]
) -> None:
    r = getattr(client, metodo)(rota, **kwargs)
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.usefixtures("exigir_login")
@pytest.mark.parametrize(("metodo", "rota", "kwargs"), ROTAS_PROTEGIDAS)
def test_login_exigido_com_token_200(
    client: TestClient, metodo: str, rota: str, kwargs: dict[str, object]
) -> None:
    token = _cadastrar(client)["access_token"]
    assert getattr(client, metodo)(rota, headers=_bearer(token), **kwargs).status_code == 200


@pytest.mark.usefixtures("exigir_login")
def test_rotas_publicas_continuam_abertas(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    r = client.get("/api/v1/medications/autocomplete", params={"q": "losartana"})
    assert r.status_code == 200


def test_openapi_documenta_401_e_o_esquema_bearer() -> None:
    doc = app.openapi()
    assert "HTTPBearer" in doc["components"]["securitySchemes"]
    for metodo, rota, _ in ROTAS_PROTEGIDAS:
        assert "401" in doc["paths"][rota][metodo]["responses"], rota


def test_cors_libera_o_cabecalho_authorization(client: TestClient) -> None:
    r = client.options(
        AUDIT,
        headers={
            "Origin": "http://localhost:8081",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert r.status_code == 200
    assert "authorization" in r.headers["access-control-allow-headers"].lower()


# --- Subida fora do local -----------------------------------------------------------


def test_producao_sem_banco_nem_segredos_nao_sobe() -> None:
    codigo = (
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "try:\n"
        "    with TestClient(app):\n"
        "        pass\n"
        "except RuntimeError as exc:\n"
        "    msg = str(exc)\n"
        "    assert 'APP_DATABASE_URL' in msg and 'APP_AUTH_JWT_SECRET' in msg, msg\n"
        "    assert 'APP_AUTH_CPF_PEPPER' in msg, msg\n"
        "else:\n"
        "    raise SystemExit('subiu sem configuracao')\n"
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith("APP_")}
    env["APP_ENVIRONMENT"] = "producao"
    r = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=PASTA_BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr[-2000:]
