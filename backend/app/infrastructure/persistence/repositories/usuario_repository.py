"""Adaptadores do repositório de usuários: Postgres (produção) e memória (testes/local)."""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.application.autenticacao import UsuarioRepositoryPort
from app.domain.usuario import SessaoRefresh, Usuario

# Idempotente: roda a cada subida. Mudanças de schema futuras entram como
# novos comandos `IF NOT EXISTS`/`ALTER ... IF NOT EXISTS` aqui.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS usuarios (
    id                uuid PRIMARY KEY,
    cpf_hmac          bytea NOT NULL UNIQUE,
    senha_hash        text NOT NULL,
    criado_em         timestamptz NOT NULL,
    tentativas_falhas integer NOT NULL DEFAULT 0,
    bloqueado_ate     timestamptz
);
CREATE TABLE IF NOT EXISTS sessoes_refresh (
    id          uuid PRIMARY KEY,
    usuario_id  uuid NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    familia     uuid NOT NULL,
    token_hash  bytea NOT NULL UNIQUE,
    expira_em   timestamptz NOT NULL,
    revogado_em timestamptz
);
CREATE INDEX IF NOT EXISTS sessoes_refresh_familia_idx ON sessoes_refresh (familia);
CREATE INDEX IF NOT EXISTS sessoes_refresh_usuario_idx ON sessoes_refresh (usuario_id);
"""


def _usuario(linha: dict[str, Any] | None) -> Usuario | None:
    if linha is None:
        return None
    return Usuario(
        id=linha["id"],
        cpf_hmac=bytes(linha["cpf_hmac"]),
        senha_hash=linha["senha_hash"],
        criado_em=linha["criado_em"],
        tentativas_falhas=linha["tentativas_falhas"],
        bloqueado_ate=linha["bloqueado_ate"],
    )


def _sessao(linha: dict[str, Any] | None) -> SessaoRefresh | None:
    if linha is None:
        return None
    return SessaoRefresh(
        id=linha["id"],
        usuario_id=linha["usuario_id"],
        familia=linha["familia"],
        token_hash=bytes(linha["token_hash"]),
        expira_em=linha["expira_em"],
        revogado_em=linha["revogado_em"],
    )


class PostgresUsuarioRepository(UsuarioRepositoryPort):
    """Todas as consultas usam parâmetros (%s): nenhuma concatenação de SQL."""

    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 10) -> None:
        self.pool = ConnectionPool(
            dsn,
            min_size=min_size,
            max_size=max_size,
            open=True,
            kwargs={"row_factory": dict_row, "connect_timeout": 5},
        )

    def criar_schema(self) -> None:
        with self.pool.connection() as conn:
            conn.execute(SCHEMA_SQL)

    def fechar(self) -> None:
        self.pool.close()

    def _um(self, sql: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            return conn.execute(sql, params).fetchone()  # type: ignore[return-value]

    def _executar(self, sql: str, params: tuple[Any, ...]) -> int:
        with self.pool.connection() as conn:
            return conn.execute(sql, params).rowcount

    def buscar_por_cpf_hmac(self, cpf_hmac: bytes) -> Usuario | None:
        return _usuario(self._um("SELECT * FROM usuarios WHERE cpf_hmac = %s", (cpf_hmac,)))

    def buscar_por_id(self, usuario_id: UUID) -> Usuario | None:
        return _usuario(self._um("SELECT * FROM usuarios WHERE id = %s", (usuario_id,)))

    def criar(self, usuario: Usuario) -> bool:
        return (
            self._executar(
                "INSERT INTO usuarios (id, cpf_hmac, senha_hash, criado_em) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (cpf_hmac) DO NOTHING",
                (usuario.id, usuario.cpf_hmac, usuario.senha_hash, usuario.criado_em),
            )
            == 1
        )

    def registrar_falha(
        self, usuario_id: UUID, *, max_tentativas: int, bloquear_ate: datetime
    ) -> None:
        # Um único UPDATE: duas tentativas simultâneas não "perdem" uma falha.
        self._executar(
            "UPDATE usuarios SET "
            "bloqueado_ate = CASE WHEN tentativas_falhas + 1 >= %s THEN %s ELSE bloqueado_ate END, "
            "tentativas_falhas = CASE WHEN tentativas_falhas + 1 >= %s THEN 0 "
            "ELSE tentativas_falhas + 1 END "
            "WHERE id = %s",
            (max_tentativas, bloquear_ate, max_tentativas, usuario_id),
        )

    def zerar_falhas(self, usuario_id: UUID) -> None:
        self._executar(
            "UPDATE usuarios SET tentativas_falhas = 0, bloqueado_ate = NULL WHERE id = %s",
            (usuario_id,),
        )

    def atualizar_senha_hash(self, usuario_id: UUID, senha_hash: str) -> None:
        self._executar(
            "UPDATE usuarios SET senha_hash = %s WHERE id = %s", (senha_hash, usuario_id)
        )

    def salvar_sessao(self, sessao: SessaoRefresh) -> None:
        with self.pool.connection() as conn:
            # Faxina barata: sessões vencidas deste usuário saem junto.
            conn.execute(
                "DELETE FROM sessoes_refresh WHERE usuario_id = %s AND expira_em < now()",
                (sessao.usuario_id,),
            )
            conn.execute(
                "INSERT INTO sessoes_refresh "
                "(id, usuario_id, familia, token_hash, expira_em) VALUES (%s, %s, %s, %s, %s)",
                (sessao.id, sessao.usuario_id, sessao.familia, sessao.token_hash, sessao.expira_em),
            )

    def buscar_sessao_por_hash(self, token_hash: bytes) -> SessaoRefresh | None:
        return _sessao(
            self._um("SELECT * FROM sessoes_refresh WHERE token_hash = %s", (token_hash,))
        )

    def revogar_sessao(self, sessao_id: UUID, agora: datetime) -> bool:
        return (
            self._executar(
                "UPDATE sessoes_refresh SET revogado_em = %s WHERE id = %s AND revogado_em IS NULL",
                (agora, sessao_id),
            )
            == 1
        )

    def revogar_familia(self, familia: UUID, agora: datetime) -> None:
        self._executar(
            "UPDATE sessoes_refresh SET revogado_em = %s "
            "WHERE familia = %s AND revogado_em IS NULL",
            (agora, familia),
        )


class MemoriaUsuarioRepository(UsuarioRepositoryPort):
    """Mesmo contrato do Postgres, em memória. Só para testes e uso local."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._usuarios: dict[UUID, Usuario] = {}
        self._sessoes: dict[UUID, SessaoRefresh] = {}

    def buscar_por_cpf_hmac(self, cpf_hmac: bytes) -> Usuario | None:
        with self._lock:
            return next((u for u in self._usuarios.values() if u.cpf_hmac == cpf_hmac), None)

    def buscar_por_id(self, usuario_id: UUID) -> Usuario | None:
        with self._lock:
            return self._usuarios.get(usuario_id)

    def criar(self, usuario: Usuario) -> bool:
        with self._lock:
            if any(u.cpf_hmac == usuario.cpf_hmac for u in self._usuarios.values()):
                return False
            self._usuarios[usuario.id] = usuario
            return True

    def registrar_falha(
        self, usuario_id: UUID, *, max_tentativas: int, bloquear_ate: datetime
    ) -> None:
        with self._lock:
            u = self._usuarios.get(usuario_id)
            if u is None:
                return
            falhas = u.tentativas_falhas + 1
            if falhas >= max_tentativas:
                self._usuarios[usuario_id] = replace(
                    u, tentativas_falhas=0, bloqueado_ate=bloquear_ate
                )
            else:
                self._usuarios[usuario_id] = replace(u, tentativas_falhas=falhas)

    def zerar_falhas(self, usuario_id: UUID) -> None:
        with self._lock:
            u = self._usuarios.get(usuario_id)
            if u is not None:
                self._usuarios[usuario_id] = replace(u, tentativas_falhas=0, bloqueado_ate=None)

    def atualizar_senha_hash(self, usuario_id: UUID, senha_hash: str) -> None:
        with self._lock:
            u = self._usuarios.get(usuario_id)
            if u is not None:
                self._usuarios[usuario_id] = replace(u, senha_hash=senha_hash)

    def salvar_sessao(self, sessao: SessaoRefresh) -> None:
        with self._lock:
            self._sessoes[sessao.id] = sessao

    def buscar_sessao_por_hash(self, token_hash: bytes) -> SessaoRefresh | None:
        with self._lock:
            return next((s for s in self._sessoes.values() if s.token_hash == token_hash), None)

    def revogar_sessao(self, sessao_id: UUID, agora: datetime) -> bool:
        with self._lock:
            s = self._sessoes.get(sessao_id)
            if s is None or s.revogado_em is not None:
                return False
            self._sessoes[sessao_id] = replace(s, revogado_em=agora)
            return True

    def revogar_familia(self, familia: UUID, agora: datetime) -> None:
        with self._lock:
            for sid, s in list(self._sessoes.items()):
                if s.familia == familia and s.revogado_em is None:
                    self._sessoes[sid] = replace(s, revogado_em=agora)
