from datetime import date

from pydantic import BaseModel, Field


class MedicationItemDTO(BaseModel):
    """Item de medicamento recebido na requisição HTTP da API."""

    nome_digitado: str = Field(
        ...,
        min_length=2,
        description="Nome informado pelo cidadão ou selecionado no autocomplete",
        examples=["Losartana Potássica 50mg"],
    )
    principio_ativo_dcb: str | None = Field(
        default=None,
        description="DCB padronizada se selecionada no autocomplete",
        examples=["LOSARTANA POTASSICA"],
    )
    concentracao: str | None = Field(
        default=None,
        examples=["50mg"],
    )
    forma_farmaceutica: str | None = Field(
        default=None,
        examples=["comprimido"],
    )
    posologia: str | None = Field(
        default=None,
        examples=["1x ao dia pela manhã"],
    )


class PrescriptionAuditRequestDTO(BaseModel):
    """Payload da requisição HTTP POST /api/v1/prescriptions/audit."""

    itens: list[MedicationItemDTO] = Field(
        ...,
        min_length=1,
        description="Lista com ao menos um medicamento a ser auditado",
    )
    data_emissao: date = Field(
        default_factory=date.today,
        description="Data de emissão da receita médica",
    )
    regiao_administrativa: str = Field(
        default="Distrito Federal",
        description="Região Administrativa (RA) ou cidade do cidadão no DF",
        examples=["Ceilândia"],
    )
    pergunta_adicional: str | None = Field(
        default=None,
        description="Dúvida administrativa ou logística complementar informada pelo cidadão",
    )
