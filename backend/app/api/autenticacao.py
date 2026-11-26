"""Rotas /api/v1/auth, composição do serviço e a dependência que protege as rotas.

Exigência de login (APP_AUTH_OBRIGATORIA, automático = fora do local):
- ligada: rota protegida sem token válido recebe 401;
- desligada (local): sem token passa como anônimo, mas um token presente e
  inválido continua recebendo 401 — o app vê o mesmo comportamento nos dois modos.
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.erro import CORPO_MALFORMADO, MUITAS_REQUISICOES, NAO_AUTENTICADO, _resposta
from app.application.autenticacao import (
    AutenticacaoService,
    CadastroIndisponivel,
    ConfigAutenticacao,
    CredenciaisInvalidas,
    TokenInvalido,
    UsuarioRepositoryPort,
)
from app.core.config import Settings, settings
from app.domain.usuario import SENHA_MAX, CpfInvalido, SenhaFraca
from app.infrastructure.persistence.repositories.usuario_repository import (
    MemoriaUsuarioRepository,
    PostgresUsuarioRepository,
)

logger = logging.getLogger("app.auth")

MENSAGEM_CREDENCIAIS = "CPF ou senha inválidos."
CABECALHO_BEARER = {"WWW-Authenticate": "Bearer"}

# --- Composição -----------------------------------------------------------------


def construir_autenticacao(cfg: Settings) -> tuple[AutenticacaoService, UsuarioRepositoryPort]:
    """Monta o serviço. Fora do local, falha na subida se faltar banco ou segredo."""
    jwt_secret = cfg.auth_jwt_secret.get_secret_value().encode()
    pepper = cfg.auth_cpf_pepper.get_secret_value().encode()
    dsn = cfg.database_url.get_secret_value()

    if not cfg.ambiente_local:
        faltando = [
            nome
            for nome, valor in (
                ("APP_DATABASE_URL", dsn),
                ("APP_AUTH_JWT_SECRET", jwt_secret),
                ("APP_AUTH_CPF_PEPPER", pepper),
            )
            if not valor
        ]
        if faltando:
            raise RuntimeError(
                "Autenticação sem configuração obrigatória fora do local: " + ", ".join(faltando)
            )
    if not jwt_secret:
        logger.warning("APP_AUTH_JWT_SECRET vazio: chave aleatória só desta subida (local)")
        jwt_secret = secrets.token_bytes(32)
    if not pepper:
        logger.warning("APP_AUTH_CPF_PEPPER vazio: pimenta aleatória só desta subida (local)")
        pepper = secrets.token_bytes(32)

    repo: UsuarioRepositoryPort
    if dsn:
        postgres = PostgresUsuarioRepository(dsn)
        postgres.criar_schema()
        repo = postgres
    else:
        logger.warning("APP_DATABASE_URL vazio: usuários em memória, somem ao reiniciar (local)")
        repo = MemoriaUsuarioRepository()

    config = ConfigAutenticacao(
        jwt_secret=jwt_secret,
        cpf_pepper=pepper,
        issuer=cfg.auth_issuer,
        audience=cfg.auth_audience,
        access_ttl=timedelta(minutes=cfg.auth_access_ttl_min),
        refresh_ttl=timedelta(days=cfg.auth_refresh_ttl_dias),
        max_tentativas=cfg.auth_max_tentativas,
        bloqueio=timedelta(minutes=cfg.auth_bloqueio_min),
    )
    return AutenticacaoService(repo, config), repo


_servico: AutenticacaoService | None = None
# Vale desde a importação: mesmo sem lifespan (TestClient sem `with`), a exigência
# segue o ambiente. Fora do local, sem serviço configurado, a rota responde 401/503.
_exigida: bool = settings.auth_exigida


def configurar(servico: AutenticacaoService | None, *, exigida: bool) -> None:
    global _servico, _exigida
    _servico = servico
    _exigida = exigida


def obter_servico() -> AutenticacaoService:
    if _servico is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Autenticação indisponível")
    return _servico


# --- Dependência das rotas protegidas -----------------------------------------------

_bearer = HTTPBearer(auto_error=False, description="Access token de /api/v1/auth/login")


def exigir_usuario(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UUID | None:
    """Id do usuário autenticado, ou None quando o login não é exigido e não há token."""
    if credenciais is None:
        if _exigida:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "Login necessário", headers=CABECALHO_BEARER
            )
        return None
    try:
        return obter_servico().validar_access(credenciais.credentials)
    except TokenInvalido:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token inválido ou expirado", headers=CABECALHO_BEARER
        ) from None


ROTA_COM_LOGIN = [Depends(exigir_usuario)]

# --- Rotas ------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1/auth", tags=["autenticacao"])


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CredenciaisDTO(_Entrada):
    cpf: str = Field(min_length=11, max_length=14, description="Com ou sem pontuação")
    senha: str = Field(min_length=1, max_length=SENHA_MAX)


class RefreshDTO(_Entrada):
    refresh_token: str = Field(min_length=20, max_length=200)


class TokensDTO(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Validade do access token, em segundos")


class EuDTO(BaseModel):
    id: UUID


_ERROS_AUTH: dict[int | str, dict[str, Any]] = {
    **CORPO_MALFORMADO,
    **MUITAS_REQUISICOES,
    401: _resposta("CPF ou senha inválidos (mensagem única, sem dizer qual)"),
}


@router.post(
    "/cadastro",
    response_model=TokensDTO,
    status_code=status.HTTP_201_CREATED,
    responses={
        **CORPO_MALFORMADO,
        **MUITAS_REQUISICOES,
        409: _resposta("Não foi possível concluir o cadastro com este CPF"),
    },
)
def cadastrar(payload: CredenciaisDTO) -> TokensDTO:
    """Cria a conta. O servidor guarda só o HMAC do CPF e o hash Argon2id da senha."""
    try:
        tokens = obter_servico().cadastrar(payload.cpf, payload.senha)
    except (CpfInvalido, SenhaFraca) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    except CadastroIndisponivel:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Não foi possível concluir o cadastro com este CPF."
        ) from None
    logger.info("cadastro concluido")
    return TokensDTO(**tokens.__dict__)


@router.post("/login", response_model=TokensDTO, responses=_ERROS_AUTH)
def login(payload: CredenciaisDTO) -> TokensDTO:
    try:
        tokens = obter_servico().entrar(payload.cpf, payload.senha)
    except CredenciaisInvalidas:
        logger.info("login recusado")
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, MENSAGEM_CREDENCIAIS, headers=CABECALHO_BEARER
        ) from None
    return TokensDTO(**tokens.__dict__)


@router.post("/refresh", response_model=TokensDTO, responses=_ERROS_AUTH)
def renovar(payload: RefreshDTO) -> TokensDTO:
    """Troca o refresh por um par novo. O refresh usado deixa de valer na hora."""
    try:
        tokens = obter_servico().renovar(payload.refresh_token)
    except CredenciaisInvalidas:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sessão expirada. Entre de novo.",
            headers=CABECALHO_BEARER,
        ) from None
    return TokensDTO(**tokens.__dict__)


@router.post(
    "/sair",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**CORPO_MALFORMADO, **MUITAS_REQUISICOES},
)
def sair(payload: RefreshDTO) -> None:
    """Encerra a sessão deste aparelho (idempotente)."""
    obter_servico().sair(payload.refresh_token)


@router.get("/eu", response_model=EuDTO, responses={**NAO_AUTENTICADO, **MUITAS_REQUISICOES})
def eu(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> EuDTO:
    """Confere o token. Exige token mesmo quando o login não é obrigatório."""
    if credenciais is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Login necessário", headers=CABECALHO_BEARER
        )
    try:
        return EuDTO(id=obter_servico().validar_access(credenciais.credentials))
    except TokenInvalido:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token inválido ou expirado", headers=CABECALHO_BEARER
        ) from None
