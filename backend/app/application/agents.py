"""Contratos da orquestração, independentes de HTTP e LangGraph."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from app.application.ports import AuditResult, RetrievalHitDTO
from app.domain.guidance import CitizenGuidanceCard
from app.domain.prescription import MedicationItemInput, PrescriptionAuditRequest


class AgentRequest(PrescriptionAuditRequest):
    itens: list[MedicationItemInput] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def require_content(self) -> AgentRequest:
        if not self.itens and not (self.pergunta_adicional or "").strip():
            raise ValueError("Informe itens ou pergunta_adicional")
        return self


class AuditorPort(Protocol):
    def executar_com_evidencias(
        self, request: PrescriptionAuditRequest, *, already_triaged: bool = False
    ) -> AuditResult: ...


class AgentTrace(BaseModel):
    agent: str
    elapsed_ms: float
    status: str = "CONCLUIDO"


class GenerationMetadata(BaseModel):
    status: Literal[
        "DETERMINISTICO",
        "GERADO",
        "FALHA_PROVEDOR",
        "SAIDA_REJEITADA",
        "CONTEXTO_REJEITADO",
        "ABSTENCAO",
        "BLOQUEADO",
    ] = "DETERMINISTICO"
    provider: str | None = None
    model: str | None = None
    latency_ms: float = 0.0
    error_code: str | None = None
    fallback_used: bool = False
    prompt_version: str | None = None
    context_chunk_ids: list[str] = Field(default_factory=list)
    context_truncated: bool = False


class AgentResponse(BaseModel):
    card: CitizenGuidanceCard
    resposta_adicional: str | None = None
    primary_route: str
    evidencias: list[RetrievalHitDTO] = Field(default_factory=list)
    citacoes: list[str] = Field(default_factory=list)
    generation: GenerationMetadata = Field(default_factory=GenerationMetadata)
    agent_trace: list[AgentTrace] = Field(default_factory=list)
    scientific_status: Literal["NAO_AVALIADO"] = "NAO_AVALIADO"


class GenerationFailure(RuntimeError):
    """Falha explícita; coleta estrita nunca substitui inferência por fallback."""

    def __init__(self, metadata: GenerationMetadata) -> None:
        super().__init__(metadata.error_code or metadata.status)
        self.metadata = metadata


class OrchestratorPort(Protocol):
    def executar(self, request: AgentRequest, *, strict: bool = False) -> AgentResponse: ...
