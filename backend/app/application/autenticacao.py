"""Autenticação por CPF e senha com tokens de acesso curtos e refresh rotativo.

Decisões (ver docs/security/autenticacao.md):
- Senha com Argon2id (argon2-cffi, parâmetros RFC 9106 de baixa memória).
- CPF nunca guardado em claro: o banco só vê HMAC-SHA256(CPF, pimenta).
- Access token JWT HS256 de 15 min, validado sem ir ao banco.
- Refresh token opaco (256 bits), guardado só como SHA-256, trocado a cada uso.
  Reapresentar um refresh já trocado revoga a família inteira daquele login:
  se um token vazou, quem roubou e o dono legítimo perdem a sessão juntos.
- Mensagem única "CPF ou senha inválidos" e verificação de hash mesmo quando o
  CPF não existe: o tempo de resposta não denuncia quem tem cadastro.
- Bloqueio temporário após N falhas seguidas, além do rate limit por IP.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.domain.usuario import (
    SessaoRefresh,
    Usuario,
    normalizar_cpf,
    validar_senha,
)

ALGORITMO_JWT = "HS256"
MIN_BYTES_SEGREDO = 32


class CredenciaisInvalidas(Exception):
    """Login ou refresh recusado. A mensagem é sempre a mesma, de propósito."""


class CadastroIndisponivel(Exception):
    """O CPF já tem conta (ou o cadastro não pôde ser concluído)."""


class TokenInvalido(Exception):
    pass


class UsuarioRepositoryPort(ABC):
    """Persistência de usuários e sessões de refresh."""

    @abstractmethod
    def buscar_por_cpf_hmac(self, cpf_hmac: bytes) -> Usuario | None: ...

    @abstractmethod
    def buscar_por_id(self, usuario_id: UUID) -> Usuario | None: ...

    @abstractmethod
    def criar(self, usuario: Usuario) -> bool:
        """Grava o usuário. Devolve False se o CPF já existe (sem levantar)."""

    @abstractmethod
    def registrar_falha(
        self, usuario_id: UUID, *, max_tentativas: int, bloquear_ate: datetime
    ) -> None:
        """Soma uma falha; ao chegar no máximo, bloqueia e zera o contador (atômico)."""

    @abstractmethod
    def zerar_falhas(self, usuario_id: UUID) -> None: ...

    @abstractmethod
    def atualizar_senha_hash(self, usuario_id: UUID, senha_hash: str) -> None: ...

    @abstractmethod
    def salvar_sessao(self, sessao: SessaoRefresh) -> None: ...

    @abstractmethod
    def buscar_sessao_por_hash(self, token_hash: bytes) -> SessaoRefresh | None: ...

    @abstractmethod
    def revogar_sessao(self, sessao_id: UUID, agora: datetime) -> bool:
        """Revoga se ainda ativa. True só para quem revogou: corrida = reuso."""

    @abstractmethod
    def revogar_familia(self, familia: UUID, agora: datetime) -> None: ...


@dataclass(frozen=True)
class Tokens:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


@dataclass(frozen=True)
class ConfigAutenticacao:
    jwt_secret: bytes
    cpf_pepper: bytes
    issuer: str
    audience: str
    access_ttl: timedelta
    refresh_ttl: timedelta
    max_tentativas: int
    bloqueio: timedelta

    def __post_init__(self) -> None:
        if len(self.jwt_secret) < MIN_BYTES_SEGREDO:
            raise ValueError(f"APP_AUTH_JWT_SECRET precisa de ao menos {MIN_BYTES_SEGREDO} bytes")
        if len(self.cpf_pepper) < MIN_BYTES_SEGREDO:
            raise ValueError(f"APP_AUTH_CPF_PEPPER precisa de ao menos {MIN_BYTES_SEGREDO} bytes")


def _agora_utc() -> datetime:
    return datetime.now(UTC)


def _hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


class AutenticacaoService:
    def __init__(
        self,
        repo: UsuarioRepositoryPort,
        config: ConfigAutenticacao,
        *,
        hasher: PasswordHasher | None = None,
        relogio: Callable[[], datetime] = _agora_utc,
    ) -> None:
        self.repo = repo
        self.config = config
        self.hasher = hasher or PasswordHasher()
        self.relogio = relogio
        # Hash de referência: quando o CPF não existe, verificamos contra ele para
        # gastar o mesmo tempo de um login com CPF cadastrado.
        self._hash_fantasma = self.hasher.hash(secrets.token_urlsafe(24))

    # --- Cadastro e login ------------------------------------------------------

    def cpf_hmac(self, cpf_digitos: str) -> bytes:
        return hmac.new(self.config.cpf_pepper, cpf_digitos.encode("ascii"), "sha256").digest()

    def cadastrar(self, cpf: str, senha: str) -> Tokens:
        """Cria a conta e já devolve a sessão.

        Levanta CpfInvalido, SenhaFraca ou CadastroIndisponivel.
        """
        digitos = normalizar_cpf(cpf)
        validar_senha(senha, digitos)
        usuario = Usuario(
            id=uuid.uuid4(),
            cpf_hmac=self.cpf_hmac(digitos),
            senha_hash=self.hasher.hash(senha),
            criado_em=self.relogio(),
        )
        if not self.repo.criar(usuario):
            raise CadastroIndisponivel
        return self._emitir(usuario.id, familia=uuid.uuid4())

    def entrar(self, cpf: str, senha: str) -> Tokens:
        try:
            digitos = normalizar_cpf(cpf)
        except ValueError:
            self._verificar(self._hash_fantasma, senha)
            raise CredenciaisInvalidas from None
        usuario = self.repo.buscar_por_cpf_hmac(self.cpf_hmac(digitos))
        if usuario is None:
            self._verificar(self._hash_fantasma, senha)
            raise CredenciaisInvalidas
        agora = self.relogio()
        if usuario.bloqueado_ate is not None and usuario.bloqueado_ate > agora:
            # Bloqueado: nem verifica a senha (não deixa o atacante continuar testando),
            # mas gasta o mesmo tempo e devolve a mesma mensagem.
            self._verificar(self._hash_fantasma, senha)
            raise CredenciaisInvalidas
        if not self._verificar(usuario.senha_hash, senha):
            self.repo.registrar_falha(
                usuario.id,
                max_tentativas=self.config.max_tentativas,
                bloquear_ate=agora + self.config.bloqueio,
            )
            raise CredenciaisInvalidas
        self.repo.zerar_falhas(usuario.id)
        if self.hasher.check_needs_rehash(usuario.senha_hash):
            self.repo.atualizar_senha_hash(usuario.id, self.hasher.hash(senha))
        return self._emitir(usuario.id, familia=uuid.uuid4())

    def _verificar(self, senha_hash: str, senha: str) -> bool:
        try:
            return self.hasher.verify(senha_hash, senha)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    # --- Refresh e saída -------------------------------------------------------

    def renovar(self, refresh_token: str) -> Tokens:
        agora = self.relogio()
        sessao = self.repo.buscar_sessao_por_hash(_hash_token(refresh_token))
        if sessao is None:
            raise CredenciaisInvalidas
        if sessao.revogado_em is not None:
            # Reuso de um refresh já trocado: sinal de roubo. Derruba o login inteiro.
            self.repo.revogar_familia(sessao.familia, agora)
            raise CredenciaisInvalidas
        if sessao.expira_em <= agora:
            raise CredenciaisInvalidas
        if not self.repo.revogar_sessao(sessao.id, agora):
            # Outra requisição trocou este mesmo token ao mesmo tempo: trata como reuso.
            self.repo.revogar_familia(sessao.familia, agora)
            raise CredenciaisInvalidas
        if self.repo.buscar_por_id(sessao.usuario_id) is None:
            raise CredenciaisInvalidas
        return self._emitir(sessao.usuario_id, familia=sessao.familia)

    def sair(self, refresh_token: str) -> None:
        """Encerra a sessão deste aparelho. Token desconhecido não é erro (idempotente)."""
        sessao = self.repo.buscar_sessao_por_hash(_hash_token(refresh_token))
        if sessao is not None:
            self.repo.revogar_familia(sessao.familia, self.relogio())

    # --- Tokens ----------------------------------------------------------------

    def _emitir(self, usuario_id: UUID, *, familia: UUID) -> Tokens:
        agora = self.relogio()
        claims: dict[str, Any] = {
            "sub": str(usuario_id),
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "iat": agora,
            "nbf": agora,
            "exp": agora + self.config.access_ttl,
            "jti": uuid.uuid4().hex,
            "typ": "access",
        }
        access = jwt.encode(claims, self.config.jwt_secret, algorithm=ALGORITMO_JWT)
        refresh = secrets.token_urlsafe(32)
        self.repo.salvar_sessao(
            SessaoRefresh(
                id=uuid.uuid4(),
                usuario_id=usuario_id,
                familia=familia,
                token_hash=_hash_token(refresh),
                expira_em=agora + self.config.refresh_ttl,
            )
        )
        return Tokens(
            access_token=access,
            refresh_token=refresh,
            expires_in=int(self.config.access_ttl.total_seconds()),
        )

    def validar_access(self, token: str) -> UUID:
        """Devolve o id do usuário de um access token válido ou levanta TokenInvalido."""
        try:
            claims = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[ALGORITMO_JWT],
                audience=self.config.audience,
                issuer=self.config.issuer,
                options={"require": ["exp", "iat", "nbf", "sub", "iss", "aud", "jti"]},
                # O PyJWT confere exp/nbf com o relógio real; 5 s de folga entre máquinas.
                leeway=5,
            )
            if claims.get("typ") != "access":
                raise TokenInvalido
            return UUID(claims["sub"])
        except (jwt.PyJWTError, ValueError, KeyError) as exc:
            raise TokenInvalido from exc
