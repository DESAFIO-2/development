"""Respostas de erro documentadas no OpenAPI.

A API já devolvia estes códigos corretamente, mas o contrato só declarava o 200
(e o 422 automático do FastAPI). Achado do Schemathesis (ST103), ver
docs/security/dast.md.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErroDTO(BaseModel):
    """Formato padrão de erro do FastAPI: `detail` é uma mensagem ou a lista de erros."""

    detail: str | list[dict[str, Any]] = Field(
        description="Mensagem do erro ou lista de erros de validação",
    )


def _resposta(descricao: str) -> dict[str, Any]:
    return {"model": ErroDTO, "description": descricao}


CORPO_MALFORMADO: dict[int | str, dict[str, Any]] = {
    400: _resposta("Corpo da requisição malformado (JSON inválido ou codificação inválida)"),
}

ERROS_MULTIMODAL: dict[int | str, dict[str, Any]] = {
    400: _resposta("Multipart malformado"),
    413: _resposta("Arquivo ou campo acima do limite em memória"),
    415: _resposta("Content-Type diferente de multipart/form-data ou x-www-form-urlencoded"),
    422: _resposta("Campos inválidos ou nenhum conteúdo (itens, pergunta, PDF ou áudio)"),
}
