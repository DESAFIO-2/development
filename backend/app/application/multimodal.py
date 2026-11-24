"""Contratos e portas abstratas do pipeline multimodal (Semana 5 — ADR 0008)."""

from __future__ import annotations

from datetime import date
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.application.agents import AgentResponse
from app.domain.prescription import MedicationItemInput

CanalMultimodal = Literal["texto", "pdf", "voz"]
StatusResolucaoItem = Literal[
    "EXATO_CATALOGO",
    "SUGESTAO_ORTOGRAFICA",
    "AMBIGUO_REQUER_CONFIRMACAO",
    "NAO_IDENTIFICADO",
]


class PDFExtractionDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    page_count: int
    truncated: bool = False
    extractor: str = "pypdf"
    latency_ms: float = 0.0


class AudioTranscriptionDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    language: str | None = None
    duration_seconds: float | None = None
    provider: str
    model_name: str
    latency_ms: float = 0.0
    error_code: str | None = None


class PDFExtractorPort(Protocol):
    def extrair_texto(self, conteudo: bytes) -> PDFExtractionDTO: ...


class AudioTranscriberPort(Protocol):
    def transcrever(self, conteudo: bytes, *, formato: str) -> AudioTranscriptionDTO: ...


class ExtractedFileReport(BaseModel):
    canal: Literal["pdf", "voz"]
    aceito: bool
    motivos_rejeicao: list[str] = Field(default_factory=list)
    alertas: list[str] = Field(default_factory=list)
    paginas: int | None = None
    duracao_segundos: float | None = None
    caracteres_extraidos: int = 0
    pii_tipos_mascarados: list[str] = Field(default_factory=list)
    extrator_usado: str
    latencia_ms: float = 0.0


class ExtractedCandidateItem(BaseModel):
    texto_origem: str
    dcb_sugerido: str | None = None
    concentracao_sugerida: str | None = None
    forma_sugerida: str | None = None
    origem_canal: CanalMultimodal
    status_resolucao: StatusResolucaoItem
    opcoes_autocomplete: list[str] = Field(default_factory=list)


class MultimodalRequest(BaseModel):
    itens: list[MedicationItemInput] = Field(default_factory=list, max_length=50)
    pergunta_adicional: str | None = Field(default=None, max_length=500)
    regiao_administrativa: str | None = Field(default=None, max_length=150)
    data_emissao: date | None = None
    tipo_prescritor: str = Field(default="SUS", min_length=1, max_length=50)
    pdf_bytes: bytes | None = None
    audio_bytes: bytes | None = None
    audio_filename: str | None = None
    confirmado_pelo_usuario: bool = False

    @field_validator("data_emissao")
    @classmethod
    def validar_data_emissao(cls, valor: date | None) -> date | None:
        if valor is not None and valor > date.today():
            raise ValueError("A data de emissão deve ser hoje ou anterior")
        return valor

    @model_validator(mode="after")
    def require_any_input(self) -> MultimodalRequest:
        if (
            not self.itens
            and not (self.pergunta_adicional or "").strip()
            and self.pdf_bytes is None
            and self.audio_bytes is None
        ):
            raise ValueError("Informe itens, pergunta_adicional, pdf ou audio")
        return self


class MultimodalResponse(BaseModel):
    sucesso: bool
    modalidades_recebidas: list[CanalMultimodal]
    requer_confirmacao_usuario: bool = False
    candidatos_extraidos: list[ExtractedCandidateItem] = Field(default_factory=list)
    relatorios_entrada: list[ExtractedFileReport] = Field(default_factory=list)
    resultado_agentes: AgentResponse | None = None
    motivo_falha_ou_bloqueio: str | None = None
    mensagem_orientacao: str | None = None
