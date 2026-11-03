from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class MedicationItemInput(BaseModel):
    """Representa um medicamento inserido pelo cidadão com auxílio de autocomplete."""

    nome_digitado: str = Field(
        ...,
        description="Nome do remédio digitado ou selecionado pelo usuário (ex: 'Losartana Potássica' ou 'Aradois')",
        examples=["Losartana Potássica 50mg"],
    )
    principio_ativo_dcb: Optional[str] = Field(
        default=None,
        description="Denominação Comum Brasileira (DCB) identificada ou selecionada via autocomplete",
        examples=["LOSARTANA POTASSICA"],
    )
    concentracao: Optional[str] = Field(
        default=None,
        description="Concentração do fármaco (ex: '50mg', '10mg', '850mg')",
        examples=["50mg"],
    )
    forma_farmaceutica: Optional[str] = Field(
        default=None,
        description="Forma farmacêutica (ex: 'comprimido', 'cápsula', 'xarope')",
        examples=["comprimido"],
    )
    posologia: Optional[str] = Field(
        default=None,
        description="Rotina de tomada indicada pelo médico (usada no módulo de adesão)",
        examples=["Tomar 1 comprimido pela manhã"],
    )
    quantidade_prescrita: Optional[str] = Field(
        default=None,
        description="Quantidade total solicitada na receita",
        examples=["60 comprimidos"],
    )


class PrescriptionAuditRequest(BaseModel):
    """Payload estruturado enviado pelo App React Native para auditoria no SUS."""

    itens: list[MedicationItemInput] = Field(
        ...,
        min_length=1,
        description="Lista de medicamentos prescritos preenchidos pelo cidadão",
    )
    data_emissao: date = Field(
        default_factory=date.today,
        description="Data de emissão gravada na receita médica para cálculo de validade",
    )
    regiao_administrativa: str = Field(
        default="Distrito Federal",
        description="Região Administrativa (RA) ou cidade do cidadão (ex: 'Ceilândia', 'Taguatinga')",
        examples=["Ceilândia"],
    )
    tipo_prescritor: str = Field(
        default="SUS",
        description="Origem da receita ('SUS' ou 'Particular/Convenio')",
        examples=["SUS"],
    )
    pergunta_adicional: Optional[str] = Field(
        default=None,
        description="Dúvida administrativa ou logística informada pelo cidadão (via texto ou áudio)",
        examples=["Onde retiro e o que preciso levar?"],
    )
