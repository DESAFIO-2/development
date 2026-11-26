"""Proteções de borda da API: teto de tamanho do corpo e limite de requisições por IP.

Os dois são middlewares ASGI puros (sem dependência nova) e respondem antes de
qualquer rota rodar, para que um cliente abusivo não chegue ao orquestrador,
ao parser de PDF ou ao STT.

- Teto de corpo: recusa com 413 pelo `Content-Length` e também conta os bytes
  que chegam de fato, para pegar envio em partes (chunked) sem esse cabeçalho.
- Rate limit: janela deslizante de 60 s em memória, por IP e por grupo de
  rotas. O IP vem de `scope["client"]`; atrás de proxy, rode o uvicorn com
  `--proxy-headers --forwarded-allow-ips=<ip do proxy>` para ele refletir o
  cliente real sem confiar em qualquer `X-Forwarded-For`.
  Com várias réplicas, o limite vale por réplica: em produção, repita a regra
  no proxy/gateway.
"""

from __future__ import annotations

import json
import math
import time
from collections import OrderedDict, deque
from collections.abc import Callable

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.seguranca.arquivos import MAX_BYTES_AUDIO, MAX_BYTES_PDF

ROTA_MULTIMODAL = "/api/v1/agents/multimodal"
# PDF + áudio + campos de texto + folga para as fronteiras do multipart.
MAX_CORPO_MULTIMODAL_BYTES = MAX_BYTES_AUDIO + MAX_BYTES_PDF + 1024 * 1024

GRUPO_GERAL = "geral"
GRUPO_PESADO = "pesado"
GRUPO_AUTH = "auth"

# Rotas caras (LLM, PDF, STT, auditoria completa) têm limite menor.
ROTAS_PESADAS = frozenset(
    {
        "/api/v1/agents/orchestrate",
        ROTA_MULTIMODAL,
        "/api/v1/prescriptions/audit",
    }
)
# Login e cadastro: limite curto contra força bruta e enumeração.
PREFIXO_AUTH = "/api/v1/auth/"
# Sondas de saúde do Docker/orquestrador nunca são limitadas.
ROTAS_LIVRES = frozenset({"/health"})


async def _responder_json(send: Send, status: int, detalhe: str, extras: dict[str, str]) -> None:
    corpo = json.dumps({"detail": detalhe}, ensure_ascii=False).encode("utf-8")
    cabecalhos = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(corpo)).encode()),
    ]
    cabecalhos += [(k.lower().encode(), v.encode()) for k, v in extras.items()]
    await send({"type": "http.response.start", "status": status, "headers": cabecalhos})
    await send({"type": "http.response.body", "body": corpo})


class _CorpoExcedido(HTTPException):
    """Herda de HTTPException: o FastAPI troca outros erros de leitura do corpo
    por 400, mas deixa este passar e responde 413."""

    def __init__(self) -> None:
        super().__init__(status_code=413, detail="Corpo da requisição grande demais")


class LimiteCorpoMiddleware:
    """Recusa com 413 requisições cujo corpo passa do teto da rota."""

    def __init__(self, app: ASGIApp, *, max_json_bytes: int) -> None:
        self.app = app
        self.max_json_bytes = max_json_bytes

    def _limite(self, path: str) -> int:
        return MAX_CORPO_MULTIMODAL_BYTES if path == ROTA_MULTIMODAL else self.max_json_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limite = self._limite(scope.get("path", ""))
        for nome, valor in scope.get("headers", []):
            if nome == b"content-length":
                try:
                    declarado = int(valor)
                except ValueError:
                    await _responder_json(send, 400, "Content-Length inválido", {})
                    return
                if declarado > limite:
                    await _responder_json(send, 413, "Corpo da requisição grande demais", {})
                    return

        recebidos = 0
        resposta_iniciada = False

        async def receive_contado() -> Message:
            nonlocal recebidos
            mensagem = await receive()
            if mensagem["type"] == "http.request":
                recebidos += len(mensagem.get("body", b""))
                if recebidos > limite:
                    raise _CorpoExcedido
            return mensagem

        async def send_marcado(mensagem: Message) -> None:
            nonlocal resposta_iniciada
            if mensagem["type"] == "http.response.start":
                resposta_iniciada = True
            await send(mensagem)

        try:
            await self.app(scope, receive_contado, send_marcado)
        except _CorpoExcedido:
            if resposta_iniciada:
                raise
            await _responder_json(send, 413, "Corpo da requisição grande demais", {})


def grupo_da_rota(path: str) -> str | None:
    """Grupo de rate limit da rota, ou None quando a rota não é limitada."""
    if path in ROTAS_LIVRES:
        return None
    if path.startswith(PREFIXO_AUTH):
        return GRUPO_AUTH
    if path in ROTAS_PESADAS:
        return GRUPO_PESADO
    return GRUPO_GERAL


class RateLimitMiddleware:
    """Janela deslizante de 60 s por (IP, grupo), com teto de chaves em memória."""

    JANELA_S = 60.0

    def __init__(
        self,
        app: ASGIApp,
        *,
        limites: dict[str, int],
        max_chaves: int = 10_000,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.app = app
        self.limites = limites
        self.max_chaves = max_chaves
        self.relogio = relogio
        self._janelas: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()

    def _consumir(self, chave: tuple[str, str], limite: int) -> float | None:
        """Registra a requisição; devolve os segundos de espera se passou do limite."""
        agora = self.relogio()
        janela = self._janelas.get(chave)
        if janela is None:
            janela = deque()
            self._janelas[chave] = janela
            # LRU: um ataque com muitos IPs não cresce a memória sem fim.
            while len(self._janelas) > self.max_chaves:
                self._janelas.popitem(last=False)
        else:
            self._janelas.move_to_end(chave)
        while janela and agora - janela[0] >= self.JANELA_S:
            janela.popleft()
        if len(janela) >= limite:
            return self.JANELA_S - (agora - janela[0])
        janela.append(agora)
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        grupo = grupo_da_rota(scope.get("path", ""))
        if grupo is None:
            await self.app(scope, receive, send)
            return
        cliente = scope.get("client")
        ip = cliente[0] if cliente else "desconhecido"
        espera = self._consumir((ip, grupo), self.limites[grupo])
        if espera is not None:
            await _responder_json(
                send,
                429,
                "Muitas requisições. Tente de novo em instantes.",
                {"Retry-After": str(max(1, math.ceil(espera)))},
            )
            return
        await self.app(scope, receive, send)
