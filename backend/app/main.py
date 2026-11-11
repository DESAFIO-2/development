from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.middleware import registrar_requisicao
from app.api.routes.prescriptions import router as prescriptions_router
from app.core.config import settings
from app.core.logs import configurar_logs

configurar_logs(settings.log_level)

app = FastAPI(title=settings.app_name, version=settings.version)
app.middleware("http")(registrar_requisicao)
app.include_router(health_router)
app.include_router(prescriptions_router)
