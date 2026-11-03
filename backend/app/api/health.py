from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Usado pelo Docker e pelo deploy para saber se a API está de pé."""
    return HealthResponse(status="ok", version=settings.version, environment=settings.environment)
