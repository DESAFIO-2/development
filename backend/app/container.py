"""Container de composição de serviços da API (inicializado no lifespan)."""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.orchestrator import LangGraphOrchestrator
from app.application.agents import OrchestratorPort
from app.application.catalog_labels import medication_labels
from app.application.evidence import literal_hit
from app.application.multimodal import AudioTranscriberPort, PDFExtractorPort
from app.application.ports import (
    EvidenceRepositoryPort,
    GeneratorPort,
    GuardrailPort,
    RetrievalHitDTO,
)
from app.application.use_cases.audit_prescription import AuditPrescriptionUseCase
from app.application.use_cases.process_multimodal import ProcessMultimodalUseCase
from app.core.config import settings
from app.guardrails.adapter import LocalGuardrailAdapter
from app.guardrails.clinical import ClinicalGuardrail
from app.infrastructure.llm.generator import PROMPT_VERSION_AGENTS, build_generator
from app.infrastructure.multimodal import PyPDFDigitalExtractor, build_audio_transcriber
from app.infrastructure.persistence.repositories.canonical_medication_repository import (
    LocalCanonicalMedicationRepository,
)
from app.infrastructure.persistence.repositories.evidence_chunk_repository import (
    LocalEvidenceChunkRepository,
)
from app.infrastructure.persistence.repositories.normative_chunk_repository import (
    LocalNormativeChunkRepository,
)
from app.infrastructure.persistence.repositories.pharmacy_stock_repository import (
    LocalPharmacyStockRepository,
)
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.tabular_matcher import TabularDCBMatcher
from app.seguranca.contexto import PublicContextRegistry, build_public_context


@dataclass(frozen=True)
class ServiceContainer:
    medication_repo: LocalCanonicalMedicationRepository
    chunk_repo: LocalNormativeChunkRepository
    evidence_chunk_repo: EvidenceRepositoryPort
    tabular_matcher: TabularDCBMatcher
    hybrid_retriever: HybridRetriever
    guardrail: GuardrailPort
    audit_use_case: AuditPrescriptionUseCase
    agents: OrchestratorPort
    public_context: PublicContextRegistry
    pdf_extractor: PDFExtractorPort
    audio_transcriber: AudioTranscriberPort | None
    multimodal_use_case: ProcessMultimodalUseCase
    pharmacy_stock_repo: LocalPharmacyStockRepository | None = None


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
    guardrail = LocalGuardrailAdapter(
        clinical=ClinicalGuardrail(
            label for med in medications for label in (*medication_labels(med), med.concentration)
        )
    )
    public_context = build_public_context(
        [
            *(literal_hit(e) for e in evidence_chunk_repo.listar_todos()),
            *(
                RetrievalHitDTO(
                    chunk_id=c.chunk_id,
                    score=0.0,
                    source_id=c.source_id,
                    document_title=c.document_title,
                    section=c.section,
                    page_number=c.page_number,
                    route_category=c.route_category,
                    text=c.text,
                )
                for c in chunks
            ),
        ],
        catalog_texts=(channel for med in medications for channel in med.df_channels),
    )
    audit_use_case = AuditPrescriptionUseCase(
        medication_repo=medication_repo,
        retriever=hybrid_retriever,
        guardrail=guardrail,
        tabular_matcher=tabular_matcher,
        public_context=public_context,
    )
    agents_auditor = AuditPrescriptionUseCase(
        medication_repo=medication_repo,
        retriever=hybrid_retriever,
        guardrail=guardrail,
        tabular_matcher=tabular_matcher,
        evidence_repo=evidence_chunk_repo,
        public_context=public_context,
    )
    generator = None
    if settings.agents_provider != "deterministic":
        if not settings.agents_model.strip():
            raise ValueError("APP_AGENTS_MODEL é obrigatório para geração")
        generator = build_generator(
            settings.agents_provider,
            model_name=settings.agents_model,
            timeout_seconds=settings.agents_timeout_seconds,
            prompt_version=PROMPT_VERSION_AGENTS,
            skip_input_guardrail=True,
        )
    agents = LangGraphOrchestrator(
        auditor=agents_auditor,
        guardrail=guardrail,
        retriever=hybrid_retriever,
        generator=generator,
        public_context=public_context,
    )
    pdf_extractor = PyPDFDigitalExtractor()
    audio_transcriber = build_audio_transcriber(
        settings.stt_provider,
        model_name=settings.stt_model,
        base_url=settings.stt_base_url,
        timeout_seconds=settings.stt_timeout_seconds,
    )
    multimodal_use_case = ProcessMultimodalUseCase(
        orchestrator=agents,
        guardrail=guardrail,
        tabular_matcher=tabular_matcher,
        medication_repo=medication_repo,
        retriever=hybrid_retriever,
        pdf_extractor=pdf_extractor,
        audio_transcriber=audio_transcriber,
    )
    pharmacy_stock_repo = LocalPharmacyStockRepository()
    return ServiceContainer(
        medication_repo=medication_repo,
        chunk_repo=chunk_repo,
        evidence_chunk_repo=evidence_chunk_repo,
        tabular_matcher=tabular_matcher,
        hybrid_retriever=hybrid_retriever,
        guardrail=guardrail,
        audit_use_case=audit_use_case,
        agents=agents,
        public_context=public_context,
        pdf_extractor=pdf_extractor,
        audio_transcriber=audio_transcriber,
        multimodal_use_case=multimodal_use_case,
        pharmacy_stock_repo=pharmacy_stock_repo,
    )


def build_orchestrator(
    services: ServiceContainer, generator: GeneratorPort | None
) -> LangGraphOrchestrator:
    """Compõe o grafo de agentes com um gerador específico sobre o container existente."""
    auditor = AuditPrescriptionUseCase(
        medication_repo=services.medication_repo,
        retriever=services.hybrid_retriever,
        guardrail=services.guardrail,
        tabular_matcher=services.tabular_matcher,
        evidence_repo=services.evidence_chunk_repo,
        public_context=services.public_context,
    )
    return LangGraphOrchestrator(
        auditor=auditor,
        guardrail=services.guardrail,
        retriever=services.hybrid_retriever,
        generator=generator,
        public_context=services.public_context,
    )


def build_multimodal_use_case(
    services: ServiceContainer,
    *,
    orchestrator: OrchestratorPort | None = None,
    audio_transcriber: AudioTranscriberPort | None = None,
) -> ProcessMultimodalUseCase:
    """Compõe o caso de uso multimodal reaproveitando o catálogo e o matcher do container."""
    return ProcessMultimodalUseCase(
        orchestrator=orchestrator or services.agents,
        guardrail=services.guardrail,
        tabular_matcher=services.tabular_matcher,
        medication_repo=services.medication_repo,
        retriever=services.hybrid_retriever,
        pdf_extractor=services.pdf_extractor,
        audio_transcriber=audio_transcriber,
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
