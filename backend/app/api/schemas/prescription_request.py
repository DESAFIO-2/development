import re
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

_DATA_ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

# "Visível" = qualquer caractere fora desta lista, que são exatamente os espaços
# de str.isspace(). A lista é explícita porque \s muda de motor para motor (Python,
# Rust e ECMA discordam, por exemplo, sobre \x1c-\x1f e \x85), e o mesmo padrão é
# usado no contrato (OpenAPI, que o Schemathesis lê) e na validação (Pydantic com
# o motor "python-re", busca sem âncora como no JSON Schema).
_ESPACOS = r"\t\n\x0b\x0c\r\x1c-\x1f \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000"
PADRAO_UM_VISIVEL = f"[^{_ESPACOS}]"
# Pelo menos dois caracteres visíveis. Sem isso, "0\r" passava no schema
# (2 caracteres) e virava "0" depois do strip, sendo rejeitado (Schemathesis ST202).
PADRAO_DOIS_VISIVEIS = f"{PADRAO_UM_VISIVEL}[\\s\\S]*{PADRAO_UM_VISIVEL}"


def tem_visivel(texto: str | None) -> bool:
    """True se o texto tem ao menos um caractere visível (mesmo critério do contrato)."""
    return texto is not None and re.search(PADRAO_UM_VISIVEL, texto) is not None


def _exigir_data_iso(valor: Any) -> Any:
    """Aceita só data AAAA-MM-DD (ou um `date` já construído).

    No modo permissivo, o Pydantic converte números em data como timestamp Unix:
    `"data_emissao": 0` virava 01/01/1970 e passava (Schemathesis ST201). Para a
    regra de validade da receita, um número no lugar da data é erro do cliente.
    """
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    if isinstance(valor, str) and _DATA_ISO.fullmatch(valor):
        return valor
    raise ValueError("data deve estar no formato AAAA-MM-DD")


DataISO = Annotated[date, BeforeValidator(_exigir_data_iso)]


class MedicationItemDTO(BaseModel):
    """Item de medicamento recebido na requisição HTTP da API."""

    model_config = ConfigDict(str_strip_whitespace=True, regex_engine="python-re")

    nome_digitado: str = Field(
        ...,
        min_length=2,
        max_length=500,
        pattern=PADRAO_DOIS_VISIVEIS,
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
    quantidade_prescrita: str | None = Field(
        default=None,
        max_length=200,
        examples=["60 comprimidos"],
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
    data_emissao: DataISO = Field(
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
    tipo_prescritor: str = Field(
        default="SUS",
        min_length=1,
        max_length=50,
        description="Origem da receita ('SUS' ou 'Particular/Convenio')",
        examples=["SUS"],
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
