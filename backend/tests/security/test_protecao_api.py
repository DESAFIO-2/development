"""Proteções de borda da API: teto de corpo, rate limit, cabeçalhos e /docs.

O rate limit e o /docs dependem do ambiente; aqui eles são testados direto no
middleware (com relógio falso) e num processo separado com APP_ENVIRONMENT de
produção, para não alterar o `app` global que os outros testes usam.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.middleware import CABECALHO_HSTS, CABECALHOS_SEGURANCA
from app.api.protecao import (
    GRUPO_AUTH,
    GRUPO_GERAL,
    GRUPO_PESADO,
    MAX_CORPO_MULTIMODAL_BYTES,
    RateLimitMiddleware,
    grupo_da_rota,
)
from app.core.config import Settings, settings
from app.main import app

AUDIT = "/api/v1/prescriptions/audit"
MULTIMODAL = "/api/v1/agents/multimodal"
PASTA_BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as cliente:
        yield cliente


# --- Teto do corpo ------------------------------------------------------------


def test_json_acima_do_teto_recebe_413_pelo_content_length(client: TestClient) -> None:
    corpo = b'{"itens": [' + b" " * (70 * 1024) + b"]}"
    r = client.post(AUDIT, content=corpo, headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    # O 413 sai por dentro dos cabeçalhos de segurança.
    for nome in CABECALHOS_SEGURANCA:
        assert nome in r.headers


def test_json_acima_do_teto_sem_content_length_recebe_413(client: TestClient) -> None:
    def em_partes() -> Iterator[bytes]:
        yield b'{"itens": ['
        for _ in range(80):
            yield b" " * 1024
        yield b"]}"

    r = client.post(AUDIT, content=em_partes(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_content_length_invalido_recebe_400(client: TestClient) -> None:
    r = client.post(AUDIT, content=b"{}", headers={"Content-Length": "abc"})
    assert r.status_code in (400, 413)


def test_multimodal_tem_teto_proprio_maior_que_o_do_json(client: TestClient) -> None:
    # 100 KB passa do teto JSON, mas não do teto multimodal: quem decide é a rota.
    arquivo = {"pdf": ("receita.pdf", b"%PDF-1.4\n" + b"0" * (100 * 1024), "application/pdf")}
    r = client.post(MULTIMODAL, files=arquivo, data={"texto": "onde retiro losartana?"})
    assert r.status_code != 413
    assert MAX_CORPO_MULTIMODAL_BYTES > 15 * 1024 * 1024


# --- Rate limit ---------------------------------------------------------------


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


def _app_limitado(relogio: _Relogio, max_chaves: int = 10_000) -> TestClient:
    interno = FastAPI()

    @interno.get("/health")
    def _health() -> dict[str, str]:
        return {"ok": "sim"}

    @interno.get("/api/v1/medications/autocomplete")
    def _geral() -> dict[str, str]:
        return {"ok": "sim"}

    @interno.post(AUDIT)
    def _pesado() -> dict[str, str]:
        return {"ok": "sim"}

    @interno.post("/api/v1/auth/login")
    def _login() -> dict[str, str]:
        return {"ok": "sim"}

    interno.add_middleware(
        RateLimitMiddleware,
        limites={GRUPO_GERAL: 3, GRUPO_PESADO: 2, GRUPO_AUTH: 1},
        max_chaves=max_chaves,
        relogio=relogio,
    )
    return TestClient(interno)


def test_grupos_de_rota() -> None:
    assert grupo_da_rota("/health") is None
    assert grupo_da_rota("/api/v1/auth/login") == GRUPO_AUTH
    assert grupo_da_rota(AUDIT) == GRUPO_PESADO
    assert grupo_da_rota(MULTIMODAL) == GRUPO_PESADO
    assert grupo_da_rota("/api/v1/agents/orchestrate") == GRUPO_PESADO
    assert grupo_da_rota("/api/v1/medications/autocomplete") == GRUPO_GERAL


def test_rate_limit_bloqueia_com_429_e_retry_after() -> None:
    relogio = _Relogio()
    c = _app_limitado(relogio)
    assert [c.post(AUDIT).status_code for _ in range(2)] == [200, 200]
    r = c.post(AUDIT)
    assert r.status_code == 429
    assert 1 <= int(r.headers["Retry-After"]) <= 60
    assert "detail" in r.json()


def test_rate_limit_libera_quando_a_janela_passa() -> None:
    relogio = _Relogio()
    c = _app_limitado(relogio)
    c.post("/api/v1/auth/login")
    assert c.post("/api/v1/auth/login").status_code == 429
    relogio.agora += 61
    assert c.post("/api/v1/auth/login").status_code == 200


def test_rate_limit_conta_cada_grupo_separado_e_ignora_health() -> None:
    relogio = _Relogio()
    c = _app_limitado(relogio)
    c.post("/api/v1/auth/login")
    assert c.post("/api/v1/auth/login").status_code == 429
    # Esgotar o login não afeta as outras rotas.
    assert c.get("/api/v1/medications/autocomplete").status_code == 200
    assert all(c.get("/health").status_code == 200 for _ in range(20))


def test_rate_limit_nao_cresce_a_memoria_sem_fim() -> None:
    relogio = _Relogio()
    middleware = RateLimitMiddleware(
        FastAPI(),
        limites={GRUPO_GERAL: 5, GRUPO_PESADO: 5, GRUPO_AUTH: 5},
        max_chaves=3,
        relogio=relogio,
    )
    for i in range(10):
        middleware._consumir((f"10.0.0.{i}", GRUPO_GERAL), 5)
    assert len(middleware._janelas) == 3


# --- Cabeçalhos ---------------------------------------------------------------


def test_cabecalhos_de_seguranca_em_resposta_json(client: TestClient) -> None:
    r = client.get("/health")
    for nome, valor in CABECALHOS_SEGURANCA.items():
        assert r.headers.get(nome) == valor
    # No local não há HTTPS: HSTS ficaria preso no navegador do desenvolvedor.
    assert CABECALHO_HSTS[0] not in r.headers


def test_ui_do_docs_fica_sem_csp_estrito(client: TestClient) -> None:
    r = client.get("/docs")
    assert r.status_code == 200
    assert "Content-Security-Policy" not in r.headers
    assert r.headers["X-Frame-Options"] == "DENY"


def test_hsts_fora_do_local(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Mesmo objeto que o middleware lê (app.core.config.settings).
    monkeypatch.setattr(settings, "environment", "producao")
    r = client.get("/health")
    assert r.headers[CABECALHO_HSTS[0]] == CABECALHO_HSTS[1]


# --- Padrões por ambiente -------------------------------------------------------


@pytest.mark.parametrize(
    ("ambiente", "docs", "rate_limit"),
    [
        ("local", True, False),
        ("LOCAL", True, False),
        ("producao", False, True),
        ("homolog", False, True),
    ],
)
def test_padroes_rigidos_fora_do_local(ambiente: str, docs: bool, rate_limit: bool) -> None:
    s = Settings(environment=ambiente)
    assert s.docs_expostos is docs
    assert s.rate_limit_ligado is rate_limit


def test_padroes_podem_ser_forcados() -> None:
    s = Settings(environment="producao", expor_docs=True, rate_limit_ativo=False)
    assert s.docs_expostos is True
    assert s.rate_limit_ligado is False


def test_app_de_producao_esconde_docs_e_liga_rate_limit() -> None:
    codigo = (
        "from app.main import app\n"
        "from app.api.protecao import RateLimitMiddleware\n"
        "from fastapi.testclient import TestClient\n"
        "assert app.docs_url is None and app.redoc_url is None and app.openapi_url is None\n"
        "assert any(m.cls is RateLimitMiddleware for m in app.user_middleware)\n"
        "c = TestClient(app)\n"
        "assert c.get('/docs').status_code == 404\n"
        "assert c.get('/openapi.json').status_code == 404\n"
    )
    env = {**os.environ, "APP_ENVIRONMENT": "producao"}
    env.pop("APP_EXPOR_DOCS", None)
    env.pop("APP_RATE_LIMIT_ATIVO", None)
    r = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=PASTA_BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr[-2000:]
