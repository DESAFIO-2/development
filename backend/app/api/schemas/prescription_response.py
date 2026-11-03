from datetime import date

from pydantic import BaseModel, Field


class ItemRoteiroDTO(BaseModel):
    """Item individual no roteiro de resposta da API."""

    medicamento: str
    principio_ativo_dcb: str
    via_retirada: str = Field(
        ...,
        description="FARMACIA_POPULAR, UBS_REME_DF, FARMACIA_ALTO_CUSTO ou NAO_PADRONIZADO",
    )
    local_sugerido: str
    o_que_levar: list[str]
    dias_validade_receita: int
    data_limite_validade: date
    dias_restantes: int
    alerta_vencimento_proximo: bool
    citacao_normativa: str


class PrescriptionAuditResponseDTO(BaseModel):
    """Resposta estruturada HTTP 200 para o app React Native."""

    sucesso: bool = True
    regiao_administrativa: str
    itens: list[ItemRoteiroDTO]
    resumo_acolhedor: str
    aviso_preservacao_ato_medico: str
