from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.middleware import registrar_requisicao
from app.api.routes.prescriptions import router as prescriptions_router
from app.container import build_services, set_services
from app.core.config import settings
from app.core.logs import configurar_logs

configurar_logs(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Carrega o catálogo e o índice lexical uma única vez na subida da API."""
    services = build_services()
    app.state.services = services
    set_services(services)
    try:
        yield
    finally:
        set_services(None)


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)
app.middleware("http")(registrar_requisicao)
app.include_router(health_router)
app.include_router(prescriptions_router)
