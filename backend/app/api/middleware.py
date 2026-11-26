import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from opentelemetry import trace

from app.core.config import settings
from app.core.logs import request_id_var

logger = logging.getLogger("app.http")

CABECALHO_REQUEST_ID = "X-Request-ID"

# Cabeçalhos de segurança em toda resposta, inclusive nas de erro.
# - nosniff: o navegador não "adivinha" o tipo e não executa JSON como script.
# - CORP same-origin: bloqueia embutimento por terceiros por padrão; libera
#   `cross-origin` apenas quando a requisição traz uma `Origin` explicitamente
#   autorizada em APP_CORS_ORIGINS (ex.: Expo Web), preservando same-origin em
#   Swagger, mobile nativo e verificações DAST.
# - X-Frame-Options/frame-ancestors: nenhuma resposta pode ser embutida (clickjacking).
# - Referrer-Policy no-referrer: a URL da API não vaza para terceiros.
# - Cache-Control no-store: respostas trazem dado de saúde; proxy e navegador não guardam.
# - Permissions-Policy: a API nunca precisa de câmera, microfone ou localização do navegador.
# - CSP: JSON não executa nada. Só a UI do /docs (exposta apenas no local) fica fora.
CABECALHOS_SEGURANCA = {
    "X-Content-Type-Options": "nosniff",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}
# HSTS só fora do local: em produção a API fica atrás de HTTPS.
CABECALHO_HSTS = ("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
# A UI do Swagger/ReDoc carrega script e CSS; o CSP estrito a deixaria em branco.
ROTAS_UI_DOCS = ("/docs", "/redoc")


async def aplicar_cabecalhos_seguranca(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Acrescenta os cabeçalhos de segurança sem sobrescrever os que a rota já definiu."""
    response = await call_next(request)
    origin = (request.headers.get("origin") or "").strip().rstrip("/")
    allowed_origin = bool(origin and origin in settings.cors_origins_list)
    e_ui_docs = request.url.path.startswith(ROTAS_UI_DOCS)
    for nome, valor in CABECALHOS_SEGURANCA.items():
        if nome == "Cross-Origin-Resource-Policy" and allowed_origin:
            response.headers.setdefault(nome, "cross-origin")
        elif nome == "Content-Security-Policy" and e_ui_docs:
            continue
        else:
            response.headers.setdefault(nome, valor)
    if not settings.ambiente_local:
        response.headers.setdefault(*CABECALHO_HSTS)
    if allowed_origin:
        vary = response.headers.get("Vary", "")
        if "Origin" not in vary:
            response.headers["Vary"] = f"{vary}, Origin".strip(", ")
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
