"""Entrada HTTP aditiva para o grafo da Semana 4."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import ConfigDict, Field, model_validator

from app.api.schemas.erro import CORPO_MALFORMADO
from app.api.schemas.prescription_request import (
    PADRAO_UM_VISIVEL,
    MedicationItemDTO,
    PrescriptionAuditRequestDTO,
    tem_visivel,
)
from app.application.agents import AgentRequest, AgentResponse
from app.container import get_services

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class AgentRequestDTO(PrescriptionAuditRequestDTO):
    # A regra do `require_content` também vai para o contrato (anyOf): sem isso,
    # o OpenAPI dizia que um corpo vazio era válido e a API o rejeitava
    # (Schemathesis ST202).
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        json_schema_extra={
            "anyOf": [
                {"required": ["itens"], "properties": {"itens": {"minItems": 1}}},
                {
                    "required": ["pergunta_adicional"],
                    "properties": {
                        "pergunta_adicional": {"type": "string", "pattern": PADRAO_UM_VISIVEL}
                    },
                },
            ]
        },
    )
    itens: list[MedicationItemDTO] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def require_content(self) -> AgentRequestDTO:
        if not self.itens and not tem_visivel(self.pergunta_adicional):
            raise ValueError("Informe itens ou pergunta_adicional")
        return self


@router.post("/orchestrate", response_model=AgentResponse, responses=CORPO_MALFORMADO)
def orchestrate(payload: AgentRequestDTO) -> AgentResponse:
    return get_services().agents.executar(AgentRequest.model_validate(payload.model_dump()))
