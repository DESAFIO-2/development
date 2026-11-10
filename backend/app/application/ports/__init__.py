"""Portas abstratas e contratos da camada de Aplicação (Clean Architecture)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

from app.domain.guidance import CitizenGuidanceCard
from app.domain.prescription import PrescriptionAuditRequest
from app.guardrails.clinical import ClinicalCheckResult
from app.guardrails.pii import PIIMaskingResult


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
    def verificar_ato_medico(self, pergunta: str) -> ClinicalCheckResult:
        """Avalia se a requisição viola limites clínicos."""
        ...

    @abstractmethod
    def desidentificar_dados_pessoais(self, texto: str) -> PIIMaskingResult:
        """Mascaramento prévio de PII (CPF, Cartão SUS, telefone, nome)."""
        ...


class AuditPrescriptionUseCasePort(ABC):
    """Porta de entrada para o caso de uso de auditoria de receita."""

    @abstractmethod
    def executar(self, request: PrescriptionAuditRequest) -> CitizenGuidanceCard:
        """Audita a receita médica e entrega o roteiro cidadão consolidado."""
        ...


__all__ = [
    "RetrievalHitDTO",
    "CanonicalMedicationItem",
    "RetrieverPort",
    "MedicationRepositoryPort",
    "GuardrailPort",
    "AuditPrescriptionUseCasePort",
]
