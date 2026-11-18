"""Entrada HTTP aditiva para o grafo da Semana 4."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import ConfigDict, Field, model_validator

from app.api.schemas.prescription_request import MedicationItemDTO, PrescriptionAuditRequestDTO
from app.application.agents import AgentRequest, AgentResponse
from app.container import get_services

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class AgentRequestDTO(PrescriptionAuditRequestDTO):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    itens: list[MedicationItemDTO] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def require_content(self) -> AgentRequestDTO:
        if not self.itens and not (self.pergunta_adicional or "").strip():
            raise ValueError("Informe itens ou pergunta_adicional")
        return self


@router.post("/orchestrate", response_model=AgentResponse)
def orchestrate(payload: AgentRequestDTO) -> AgentResponse:
    return get_services().agents.executar(AgentRequest.model_validate(payload.model_dump()))
