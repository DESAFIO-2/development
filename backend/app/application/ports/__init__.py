"""Portas abstratas e contratos da camada de Aplicação (Clean Architecture)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

from app.domain.guidance import CitizenGuidanceCard
from app.domain.prescription import PrescriptionAuditRequest


@dataclass(frozen=True)
class ClinicalCheckDTO:
    """Resultado da inspeção do Guardrail Clínico e ético."""

    bloqueado: bool
    motivo: str
    alerta_emergencia: bool
    mensagem_acolhedora: str


@dataclass(frozen=True)
class PIIMaskingDTO:
    """Resultado auditável da desidentificação LGPD."""

    texto_sanitizado: str
    tipos_detectados: list[str]
    total_substituicoes: int


@dataclass(frozen=True)
class RetrievalHitDTO:
    """Item recuperado com pontuação e procedência de fonte oficial."""

    chunk_id: str
    score: float
    source_id: str
    document_title: str
    section: str
    page_number: int
    route_category: str
    text: str
    matched_dcb: str | None = None
    retriever_name: str = "hybrid_dcb_rrf"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CanonicalMedicationItem:
    """Representação estruturada de medicamento canônico para busca determinística."""

    medication_id: str
    dcb_name: str
    concentration: str
    pharmaceutical_form: str
    rename_component: str
    available_pfpb: bool
    pfpb_free: bool
    available_reme_df: bool
    dispensation_route: str
    requires_lme: bool
    prescription_validity_days: int = 180
    required_documents: list[str] | None = None
    source_id: str = "RENAME_2024"
    source_page: int = 1
    notes: str = ""
    df_channels: tuple[str, ...] = ()
    occurrence_ids: tuple[str, ...] = ()
    item_type: str = "medicine"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanonicalMedicationItem:
        return cls(
            medication_id=str(data["medication_id"]),
            dcb_name=str(data["dcb_name"]).strip().lower(),
            concentration=str(data["concentration"]).strip(),
            pharmaceutical_form=str(data["pharmaceutical_form"]).strip().lower(),
            rename_component=str(data["rename_component"]),
            available_pfpb=bool(data["available_pfpb"]),
            pfpb_free=bool(data["pfpb_free"]),
            available_reme_df=bool(data["available_reme_df"]),
            dispensation_route=str(data["dispensation_route"]),
            requires_lme=bool(data["requires_lme"]),
            prescription_validity_days=int(data.get("prescription_validity_days", 180)),
            required_documents=[str(x) for x in data.get("required_documents", [])],
            source_id=str(data.get("source_id", "RENAME_2024")),
            source_page=int(data.get("source_page", 1)),
            notes=str(data.get("notes", "")),
            df_channels=tuple(str(channel) for channel in data.get("df_channels", [])),
            occurrence_ids=tuple(str(oid) for oid in data.get("occurrence_ids", [])),
            item_type=str(data.get("item_type", "medicine")),
        )


class RetrieverPort(ABC):
    """Porta para recuperação normativa e híbrida."""

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.18,
    ) -> list[RetrievalHitDTO]:
        """Recupera evidências normativas para a consulta informada."""
        ...


class MedicationRepositoryPort(ABC):
    """Porta para acesso ao catálogo canônico de medicamentos do SUS."""

    @abstractmethod
    def listar_todos(self) -> list[CanonicalMedicationItem]:
        """Retorna todos os medicamentos canônicos padronizados."""
        ...

    @abstractmethod
    def buscar_por_dcb(self, dcb_nome: str) -> list[CanonicalMedicationItem]:
        """Busca medicamentos por princípio ativo."""
        ...

    @abstractmethod
    def sugerir_autocomplete(self, termo: str, limite: int = 10) -> list[CanonicalMedicationItem]:
        """Gera sugestões de preenchimento para a barra de busca do app."""
        ...


class GuardrailPort(ABC):
    """Porta para verificação ética de Ato Médico e desidentificação LGPD."""

    @abstractmethod
    def verificar_ato_medico(self, pergunta: str) -> ClinicalCheckDTO:
        """Avalia se a requisição viola limites clínicos."""
        ...

    @abstractmethod
    def desidentificar_dados_pessoais(self, texto: str) -> PIIMaskingDTO:
        """Mascaramento prévio de PII (CPF, Cartão SUS, RG, CRM, telefone, endereço, nome)."""
        ...


class AuditPrescriptionUseCasePort(ABC):
    """Porta de entrada para o caso de uso de auditoria de receita."""

    @abstractmethod
    def executar(self, request: PrescriptionAuditRequest) -> CitizenGuidanceCard:
        """Audita a receita médica e entrega o roteiro cidadão consolidado."""
        ...


@dataclass(frozen=True)
class GenerationResultDTO:
    """Resultado imutável de síntese textual por LLM (com ou sem evidências RAG)."""

    text: str
    provider: str
    model_name: str
    grounded: bool
    latency_ms: float = 0.0
    error_code: str | None = None
    execution_kind: str = "llm"
    provider_metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceChunkDTO:
    """Representação de um chunk literal de evidência aprovada 1:1 (one-evidence-v2)."""

    chunk_id: str
    evidence_id: str
    occurrence_id: str
    medicine_id: str | None
    supply_id: str | None
    item_type: str
    source_id: str
    source_version: str
    source_url: str
    page_number: int
    source_sha256: str
    release_version: str
    text: str
    literal_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceChunkDTO:
        src = data["source"]
        text = str(data["text"]).strip()
        literal_text = str(data["literal_text"]).strip()
        if not text or not literal_text:
            raise ValueError(f"Chunk de evidência vazio: {data.get('chunk_id')!r}")
        return cls(
            chunk_id=str(data["chunk_id"]),
            evidence_id=str(data["evidence_id"]),
            occurrence_id=str(data["occurrence_id"]),
            medicine_id=str(data["medicine_id"]) if data.get("medicine_id") else None,
            supply_id=str(data["supply_id"]) if data.get("supply_id") else None,
            item_type=str(data["item_type"]),
            source_id=str(src["source_id"]),
            source_version=str(src["version"]),
            source_url=str(src["url"]),
            page_number=int(src["page"]),
            source_sha256=str(src["sha256"]),
            release_version=str(data["release_version"]),
            text=text,
            literal_text=literal_text,
        )


class EvidenceRepositoryPort(ABC):
    """Presença documental; vínculo com catálogo exclusivamente por occurrence_ids."""

    @abstractmethod
    def listar_todos(self) -> list[EvidenceChunkDTO]: ...

    @abstractmethod
    def buscar_por_chunk_id(self, chunk_id: str) -> EvidenceChunkDTO | None: ...

    @abstractmethod
    def buscar_por_occurrence_ids(
        self, occurrence_ids: list[str] | tuple[str, ...]
    ) -> list[EvidenceChunkDTO]:
        """Retorna todas as evidências solicitadas; falha se algum vínculo não existir."""
        ...


class GeneratorPort(ABC):
    """Porta abstrata para geração textual pareada (LLM sem recuperação × LLM com RAG)."""

    @abstractmethod
    def generate(
        self,
        question: str,
        evidences: tuple[RetrievalHitDTO, ...] = (),
        *,
        rag_mode: bool | None = None,
    ) -> GenerationResultDTO:
        """Sintetiza resposta em linguagem cidadã com ou sem evidências recuperadas."""
        ...

    def __call__(
        self,
        question: str,
        evidences: tuple[RetrievalHitDTO, ...] = (),
    ) -> str:
        """Permite uso direto como Callable[[str, tuple[RetrievalHitDTO, ...]], str]."""
        return self.generate(question, evidences).text


__all__ = [
    "ClinicalCheckDTO",
    "PIIMaskingDTO",
    "RetrievalHitDTO",
    "CanonicalMedicationItem",
    "RetrieverPort",
    "MedicationRepositoryPort",
    "GuardrailPort",
    "AuditPrescriptionUseCasePort",
    "GenerationResultDTO",
    "GeneratorPort",
    "EvidenceChunkDTO",
    "EvidenceRepositoryPort",
]
