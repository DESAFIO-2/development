from datetime import date

from pydantic import BaseModel

from app.domain.medication import CoverageRoute


class ItemRoteiroDTO(BaseModel):
    """Item individual no roteiro de resposta da API."""

    medicamento: str
    principio_ativo_dcb: str
    via_retirada: CoverageRoute
    local_sugerido: str
    o_que_levar: list[str]
    dias_validade_receita: int | None
    data_limite_validade: date | None
    dias_restantes: int | None
    alerta_vencimento_proximo: bool
    citacao_normativa: str


class PrescriptionAuditResponseDTO(BaseModel):
    """Resposta estruturada HTTP 200 para o app React Native."""

    sucesso: bool = True
    regiao_administrativa: str
    itens: list[ItemRoteiroDTO]
    resumo_acolhedor: str
    aviso_preservacao_ato_medico: str
