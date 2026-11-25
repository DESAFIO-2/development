import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from opentelemetry import trace

from app.core.logs import request_id_var

logger = logging.getLogger("app.http")

CABECALHO_REQUEST_ID = "X-Request-ID"

# Cabeçalhos de segurança em toda resposta, inclusive nas de erro.
# - nosniff: o navegador não "adivinha" o tipo e não executa JSON como script.
# - CORP same-origin: outro site não embute as respostas da API (dados de saúde).
#   Não afeta o app mobile, que não é navegador, nem o Swagger em /docs.
CABECALHOS_SEGURANCA = {
    "X-Content-Type-Options": "nosniff",
    "Cross-Origin-Resource-Policy": "same-origin",
}


async def aplicar_cabecalhos_seguranca(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Acrescenta os cabeçalhos de segurança sem sobrescrever os que a rota já definiu."""
    response = await call_next(request)
    for nome, valor in CABECALHOS_SEGURANCA.items():
        response.headers.setdefault(nome, valor)
    return response


async def registrar_requisicao(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Dá um ID a cada requisição, devolve no cabeçalho e registra rota, status e duração."""
    request_id = request.headers.get(CABECALHO_REQUEST_ID) or uuid.uuid4().hex
    token = request_id_var.set(request_id)
    # Grava o request_id no trace da requisição: dá para buscar por ele no Jaeger.
    trace.get_current_span().set_attribute("app.request_id", request_id)
    inicio = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers[CABECALHO_REQUEST_ID] = request_id
        # Usa o molde da rota ("/receitas/{id}") e não a URL real: evita dado pessoal no log.
        rota = getattr(request.scope.get("route"), "path", "desconhecida")
        logger.info(
            "requisicao concluida",
            extra={
                "metodo": request.method,
                "rota": rota,
                "status": response.status_code,
                "duracao_ms": round((time.perf_counter() - inicio) * 1000, 2),
            },
        )
        return response
    finally:
        request_id_var.reset(token)
