"""Container de composição de serviços da API (inicializado no lifespan)."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports import EvidenceRepositoryPort, GuardrailPort
from app.application.use_cases.audit_prescription import AuditPrescriptionUseCase
from app.guardrails.adapter import LocalGuardrailAdapter
from app.infrastructure.persistence.repositories.canonical_medication_repository import (
    LocalCanonicalMedicationRepository,
)
from app.infrastructure.persistence.repositories.evidence_chunk_repository import (
    LocalEvidenceChunkRepository,
)
from app.infrastructure.persistence.repositories.normative_chunk_repository import (
    LocalNormativeChunkRepository,
)
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.tabular_matcher import TabularDCBMatcher


@dataclass(frozen=True)
class ServiceContainer:
    medication_repo: LocalCanonicalMedicationRepository
    chunk_repo: LocalNormativeChunkRepository
    evidence_chunk_repo: EvidenceRepositoryPort
    tabular_matcher: TabularDCBMatcher
    hybrid_retriever: HybridRetriever
    guardrail: GuardrailPort
    audit_use_case: AuditPrescriptionUseCase


_cached_services: ServiceContainer | None = None


def build_services() -> ServiceContainer:
    """Instancia repositórios, matcher único e caso de uso principal."""
    medication_repo = LocalCanonicalMedicationRepository()
    chunk_repo = LocalNormativeChunkRepository()
    evidence_chunk_repo = LocalEvidenceChunkRepository()
    medications = medication_repo.listar_todos()
    # Falha fechado se o catálogo anunciar ocorrências sem evidência no pacote.
    evidence_chunk_repo.buscar_por_occurrence_ids(
        tuple(oid for med in medications for oid in med.occurrence_ids)
    )
    chunks = chunk_repo.listar_todos()
    tabular_matcher = TabularDCBMatcher(medications)
    hybrid_retriever = HybridRetriever(
        medications=medications,
        chunks=chunks,
        tabular_matcher=tabular_matcher,
    )
    guardrail = LocalGuardrailAdapter()
    audit_use_case = AuditPrescriptionUseCase(
        medication_repo=medication_repo,
        retriever=hybrid_retriever,
        guardrail=guardrail,
        tabular_matcher=tabular_matcher,
    )
    return ServiceContainer(
        medication_repo=medication_repo,
        chunk_repo=chunk_repo,
        evidence_chunk_repo=evidence_chunk_repo,
        tabular_matcher=tabular_matcher,
        hybrid_retriever=hybrid_retriever,
        guardrail=guardrail,
        audit_use_case=audit_use_case,
    )


def set_services(container: ServiceContainer | None) -> None:
    global _cached_services
    _cached_services = container


def get_services() -> ServiceContainer:
    """Retorna o container aquecido no lifespan ou inicializa sob demanda (ex.: TestClient)."""
    global _cached_services
    if _cached_services is None:
        _cached_services = build_services()
    return _cached_services
