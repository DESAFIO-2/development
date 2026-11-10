from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MedicationItemDTO(BaseModel):
    """Item de medicamento recebido na requisição HTTP da API."""

    model_config = ConfigDict(str_strip_whitespace=True)

    nome_digitado: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Nome informado pelo cidadão ou selecionado no autocomplete",
        examples=["Losartana Potássica 50mg"],
    )
    principio_ativo_dcb: str | None = Field(
        default=None,
        max_length=500,
        description="DCB padronizada se selecionada no autocomplete",
        examples=["LOSARTANA POTASSICA"],
    )
    concentracao: str | None = Field(
        default=None,
        max_length=500,
        examples=["50mg"],
    )
    forma_farmaceutica: str | None = Field(
        default=None,
        max_length=500,
        examples=["comprimido"],
    )
    posologia: str | None = Field(
        default=None,
        max_length=500,
        examples=["1x ao dia pela manhã"],
    )


class PrescriptionAuditRequestDTO(BaseModel):
    """Payload da requisição HTTP POST /api/v1/prescriptions/audit."""

    model_config = ConfigDict(str_strip_whitespace=True)

    itens: list[MedicationItemDTO] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Lista com ao menos um medicamento a ser auditado",
    )
    data_emissao: date = Field(
        default_factory=date.today,
        description="Data de emissão da receita médica",
    )
    regiao_administrativa: str = Field(
        default="Distrito Federal",
        min_length=1,
        max_length=150,
        description="Região Administrativa (RA) ou cidade do cidadão no DF",
        examples=["Ceilândia"],
    )
    pergunta_adicional: str | None = Field(
        default=None,
        max_length=500,
        description="Dúvida administrativa ou logística complementar informada pelo cidadão",
    )

    @field_validator("data_emissao")
    @classmethod
    def validar_data_emissao(cls, valor: date) -> date:
        if valor > date.today():
            raise ValueError("A data de emissão deve ser hoje ou anterior")
        return valor
