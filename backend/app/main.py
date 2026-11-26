from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.autenticacao import configurar as configurar_auth
from app.api.autenticacao import construir_autenticacao
from app.api.autenticacao import router as auth_router
from app.api.health import router as health_router
from app.api.middleware import aplicar_cabecalhos_seguranca, registrar_requisicao
from app.api.protecao import (
    GRUPO_AUTH,
    GRUPO_GERAL,
    GRUPO_PESADO,
    LimiteCorpoMiddleware,
    RateLimitMiddleware,
)
from app.api.routes.agents import router as agents_router
from app.api.routes.multimodal import router as multimodal_router
from app.api.routes.pharmacies import router as pharmacies_router
from app.api.routes.prescriptions import router as prescriptions_router
from app.container import build_services, set_services
from app.core.config import settings
from app.core.logs import configurar_logs
from app.infrastructure.persistence.repositories.usuario_repository import (
    PostgresUsuarioRepository,
)

configurar_logs(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Carrega o catálogo e o índice lexical uma única vez na subida da API."""
    services = build_services()
    app.state.services = services
    set_services(services)
    # Falha na subida (e não na primeira requisição) se faltar banco ou segredo fora do local.
    auth_service, auth_repo = construir_autenticacao(settings)
    configurar_auth(auth_service, exigida=settings.auth_exigida)
    try:
        yield
    finally:
        configurar_auth(None, exigida=settings.auth_exigida)
        if isinstance(auth_repo, PostgresUsuarioRepository):
            auth_repo.fechar()
        set_services(None)


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
    # Fora do local, sem Swagger/ReDoc/OpenAPI públicos: não entrega o mapa da API.
    docs_url="/docs" if settings.docs_expostos else None,
    redoc_url="/redoc" if settings.docs_expostos else None,
    openapi_url="/openapi.json" if settings.docs_expostos else None,
)
# Ordem: o último middleware registrado é o mais externo. Teto de corpo e rate
# limit ficam por dentro do CORS e dos cabeçalhos, para que um 413/429 também
# saia com CORS (o app web lê o erro) e com os cabeçalhos de segurança.
app.add_middleware(LimiteCorpoMiddleware, max_json_bytes=settings.max_corpo_json_bytes)
if settings.rate_limit_ligado:
    app.add_middleware(
        RateLimitMiddleware,
        limites={
            GRUPO_GERAL: settings.rate_limit_geral_por_minuto,
            GRUPO_PESADO: settings.rate_limit_pesado_por_minuto,
            GRUPO_AUTH: settings.rate_limit_auth_por_minuto,
        },
    )
if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins_list),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        # Token vai no cabeçalho Authorization (nunca em cookie): CSRF não se aplica.
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
app.middleware("http")(registrar_requisicao)
app.middleware("http")(aplicar_cabecalhos_seguranca)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(prescriptions_router)
app.include_router(pharmacies_router)
app.include_router(agents_router)
app.include_router(multimodal_router)
