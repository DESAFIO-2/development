"""Contrato do repositório de usuários: memória e Postgres precisam se comportar igual.

O Postgres só roda com APP_TESTE_DATABASE_URL definido (no CI, um serviço
Postgres efêmero; localmente, `make db-up`). Cada teste usa um schema próprio
e o apaga no fim: nunca toca nas tabelas de uso real.
"""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from app.application.autenticacao import UsuarioRepositoryPort
from app.domain.usuario import SessaoRefresh, Usuario
from app.infrastructure.persistence.repositories.usuario_repository import (
    MemoriaUsuarioRepository,
    PostgresUsuarioRepository,
)

DSN_TESTE = os.environ.get("APP_TESTE_DATABASE_URL", "")
AGORA = datetime.now(UTC).replace(microsecond=0)


def _postgres() -> Iterator[PostgresUsuarioRepository]:
    if not DSN_TESTE:
        pytest.skip("APP_TESTE_DATABASE_URL não definido")
    schema = f"teste_{uuid.uuid4().hex[:12]}"
    import psycopg

    with psycopg.connect(DSN_TESTE, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA "{schema}"')
    dsn = f"{DSN_TESTE}{'&' if '?' in DSN_TESTE else '?'}options=-csearch_path%3D{schema}"
    repo = PostgresUsuarioRepository(dsn, min_size=1, max_size=4)
    repo.criar_schema()
    try:
        yield repo
    finally:
        repo.fechar()
        with psycopg.connect(DSN_TESTE, autocommit=True) as conn:
            conn.execute(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.fixture(params=["memoria", "postgres"])
def repo(request: pytest.FixtureRequest) -> Iterator[UsuarioRepositoryPort]:
    if request.param == "memoria":
        yield MemoriaUsuarioRepository()
    else:
        yield from _postgres()


def _usuario(cpf_hmac: bytes = b"h" * 32) -> Usuario:
    return Usuario(id=uuid.uuid4(), cpf_hmac=cpf_hmac, senha_hash="$argon2id$x", criado_em=AGORA)


def _sessao(usuario_id: uuid.UUID, familia: uuid.UUID, dias: int = 30) -> SessaoRefresh:
    return SessaoRefresh(
        id=uuid.uuid4(),
        usuario_id=usuario_id,
        familia=familia,
        token_hash=uuid.uuid4().bytes * 2,
        expira_em=AGORA + timedelta(days=dias),
    )


def test_criar_e_buscar(repo: UsuarioRepositoryPort) -> None:
    u = _usuario()
    assert repo.criar(u)
    assert repo.buscar_por_cpf_hmac(u.cpf_hmac) == u
    assert repo.buscar_por_id(u.id) == u
    assert repo.buscar_por_cpf_hmac(b"x" * 32) is None
    assert repo.buscar_por_id(uuid.uuid4()) is None


def test_cpf_duplicado_devolve_false(repo: UsuarioRepositoryPort) -> None:
    assert repo.criar(_usuario())
    assert not repo.criar(_usuario())


def test_falhas_bloqueiam_no_maximo_e_zeram(repo: UsuarioRepositoryPort) -> None:
    u = _usuario()
    repo.criar(u)
    ate = AGORA + timedelta(minutes=15)
    repo.registrar_falha(u.id, max_tentativas=3, bloquear_ate=ate)
    repo.registrar_falha(u.id, max_tentativas=3, bloquear_ate=ate)
    atual = repo.buscar_por_id(u.id)
    assert atual is not None and atual.tentativas_falhas == 2 and atual.bloqueado_ate is None
    repo.registrar_falha(u.id, max_tentativas=3, bloquear_ate=ate)
    atual = repo.buscar_por_id(u.id)
    assert atual is not None and atual.tentativas_falhas == 0 and atual.bloqueado_ate == ate
    repo.zerar_falhas(u.id)
    atual = repo.buscar_por_id(u.id)
    assert atual is not None and atual.bloqueado_ate is None


def test_falhas_simultaneas_nao_se_perdem(repo: UsuarioRepositoryPort) -> None:
    u = _usuario()
    repo.criar(u)
    ate = AGORA + timedelta(minutes=15)
    threads = [
        threading.Thread(
            target=repo.registrar_falha,
            args=(u.id,),
            kwargs={"max_tentativas": 100, "bloquear_ate": ate},
        )
        for _ in range(20)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    atual = repo.buscar_por_id(u.id)
    assert atual is not None and atual.tentativas_falhas == 20


def test_atualizar_senha_hash(repo: UsuarioRepositoryPort) -> None:
    u = _usuario()
    repo.criar(u)
    repo.atualizar_senha_hash(u.id, "$argon2id$novo")
    atual = repo.buscar_por_id(u.id)
    assert atual is not None and atual.senha_hash == "$argon2id$novo"


def test_sessao_revoga_uma_vez_so(repo: UsuarioRepositoryPort) -> None:
    u = _usuario()
    repo.criar(u)
    s = _sessao(u.id, uuid.uuid4())
    repo.salvar_sessao(s)
    assert repo.buscar_sessao_por_hash(s.token_hash) == s
    assert repo.revogar_sessao(s.id, AGORA)
    assert not repo.revogar_sessao(s.id, AGORA)
    revogada = repo.buscar_sessao_por_hash(s.token_hash)
    assert revogada is not None and revogada.revogado_em == AGORA


def test_revogacao_simultanea_so_um_vence(repo: UsuarioRepositoryPort) -> None:
    u = _usuario()
    repo.criar(u)
    s = _sessao(u.id, uuid.uuid4())
    repo.salvar_sessao(s)
    resultados: list[bool] = []
    lock = threading.Lock()

    def tentar() -> None:
        r = repo.revogar_sessao(s.id, AGORA)
        with lock:
            resultados.append(r)

    threads = [threading.Thread(target=tentar) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert resultados.count(True) == 1


def test_revogar_familia_so_afeta_a_familia(repo: UsuarioRepositoryPort) -> None:
    u = _usuario()
    repo.criar(u)
    familia, outra = uuid.uuid4(), uuid.uuid4()
    a, b, c = _sessao(u.id, familia), _sessao(u.id, familia), _sessao(u.id, outra)
    for s in (a, b, c):
        repo.salvar_sessao(s)
    repo.revogar_familia(familia, AGORA)
    assert all(
        (x := repo.buscar_sessao_por_hash(s.token_hash)) is not None and x.revogado_em
        for s in (a, b)
    )
    restante = repo.buscar_sessao_por_hash(c.token_hash)
    assert restante is not None and restante.revogado_em is None
