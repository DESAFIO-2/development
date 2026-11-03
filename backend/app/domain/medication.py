from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class CoverageRoute(str, Enum):
    """Via oficial de obtenção gratuita do medicamento no SUS / DF."""

    FARMACIA_POPULAR = "FARMACIA_POPULAR"
    UBS_REME_DF = "UBS_REME_DF"
    FARMACIA_ALTO_CUSTO = "FARMACIA_ALTO_CUSTO"
    NAO_PADRONIZADO = "NAO_PADRONIZADO"


class ComponenteSUS(str, Enum):
    """Componente da Assistência Farmacêutica na RENAME."""

    CBAF = "CBAF"          # Básico (Atenção Primária / UBS)
    CEAF = "CEAF"          # Especializado (Alto Custo / LME)
    CESAF = "CESAF"        # Estratégico (Programas específicos do MS)
    NAO_APLICAVEL = "NAO_APLICAVEL"


class MedicationCoverage(BaseModel):
    """Representa a auditoria normativa e regras de dispensação de um medicamento."""

    dcb_principio_ativo: str = Field(
        ...,
        description="Denominação Comum Brasileira (DCB) oficial",
        examples=["LOSARTANA POTASSICA"],
    )
    concentracao: str = Field(
        ...,
        description="Concentração padronizada",
        examples=["50 MG"],
    )
    forma_farmaceutica: str = Field(
        default="COMPRIMIDO",
        description="Forma de apresentação",
        examples=["COMPRIMIDO"],
    )
    via_primaria: CoverageRoute = Field(
        ...,
        description="Via prioritária mais rápida e acessível para o cidadão",
    )
    disponivel_farmacia_popular: bool = Field(
        default=False,
        description="Disponível gratuitamente em farmácias privadas credenciadas via CPF",
    )
    disponivel_ubs_df: bool = Field(
        default=False,
        description="Padronizado para dispensação na farmácia da UBS (REME-DF)",
    )
    exige_lme_alto_custo: bool = Field(
        default=False,
        description="Exige abertura de processo com Laudo LME na Farmácia de Alto Custo",
    )
    validade_receita_dias: int = Field(
        default=180,
        description="Prazo legal de validade da receita médica em dias",
    )
    documentos_obrigatorios: list[str] = Field(
        default_factory=list,
        description="Lista de documentos exigidos pela portaria para a retirada",
    )
    fonte_oficial: str = Field(
        ...,
        description="Citação formal da portaria ou relação que ampara a regra",
        examples=["Portaria GM/MS nº 6.324/2024 (RENAME 2024)"],
    )
    observacoes_dispensacao: Optional[str] = Field(
        default=None,
        description="Orientações administrativas complementares",
    )
