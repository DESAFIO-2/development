from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.container import get_services
from app.core.config import settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Usado pelo Docker e pelo deploy para checar prontidão real da API e do corpus."""
    try:
        services = get_services()
        if (
            not services.medication_repo.listar_todos()
            or not services.chunk_repo.listar_todos()
            or not services.evidence_chunk_repo.listar_todos()
        ):
            raise ValueError("Corpus indisponível")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Corpus não carregado") from exc
    return HealthResponse(status="ok", version=settings.version, environment=settings.environment)
