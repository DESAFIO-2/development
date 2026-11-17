"""Segunda camada de guardrail: Llama Guard 3 local (Ollama), PRONTA PARA MEDIR.

Não está ligada no produto. A ordem é de propósito: primeiro o holdout independente
(`evals/configs/protocolo_holdout_guardrail.md`) diz se ela ajuda, depois um ADR decide
se entra na API.

- Chama o Ollama em `/api/chat` com `llama-guard3:1b`, temperatura 0 e seed 42.
- Classifica a pergunta ou, quando recebe também a resposta, a resposta (o Llama
  Guard julga a última mensagem do assistente).
- Lê `safe` ou `unsafe` + categorias (ex.: `S6`, "Specialized Advice", que cobre
  conselho médico). Qualquer `unsafe` bloqueia.
- Mascara PII antes de enviar. Log e span (`guardrail_segunda_camada`) levam só
  decisão, categorias e latência, nunca o texto (LGPD).
- Classificador fora do ar: em `producao` bloqueia (falha fechada); em `avaliacao`
  levanta erro, para a falha nunca virar acerto no relatório.

Fontes conferidas em 13/11/2026: model card da Meta e página do Ollama listam o
português entre os 8 idiomas. Nenhuma diz que o modelo é validado para triagem
clínica: é moderação genérica.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import settings
from app.core.telemetry import trace_operation
from app.guardrails.clinical import deve_bloquear as deve_bloquear_camada_1
from app.guardrails.pii import PIIMasker

logger = logging.getLogger("app.guardrails")

MODELO_PADRAO = "llama-guard3:1b"
Modo = Literal["producao", "avaliacao"]
_CATEGORIA = re.compile(r"\bS\d{1,2}\b")


class SegundaCamadaIndisponivel(RuntimeError):
    """O classificador não respondeu ou respondeu algo ilegível (só no modo avaliação)."""


@dataclass(frozen=True)
class DecisaoSegundaCamada:
    bloqueado: bool
    categorias: tuple[str, ...]
    latencia_ms: float
    falha_fechada: bool = False


def interpretar_saida(texto: str) -> tuple[bool, tuple[str, ...]]:
    """Lê a saída do Llama Guard: `safe`, ou `unsafe` seguido das categorias."""
    linhas = [linha.strip() for linha in texto.strip().splitlines() if linha.strip()]
    if not linhas:
        raise ValueError("Saída vazia do classificador")
    veredito = linhas[0].lower()
    if veredito == "safe":
        return False, ()
    if veredito == "unsafe":
        return True, tuple(_CATEGORIA.findall(" ".join(linhas[1:])))
    raise ValueError("Saída do classificador fora do formato safe/unsafe")


class ClassificadorLlamaGuard:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        modelo: str = MODELO_PADRAO,
        timeout_seconds: float = 30.0,
        modo: Modo = "producao",
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.modelo = modelo
        self.timeout_seconds = timeout_seconds
        self.modo = modo
        self._pii = PIIMasker()

    def _mensagens(self, pergunta: str, resposta: str | None) -> list[dict[str, str]]:
        mensagens = [{"role": "user", "content": self._pii.mascarar(pergunta).texto_sanitizado}]
        if resposta is not None:
            mensagens.append(
                {"role": "assistant", "content": self._pii.mascarar(resposta).texto_sanitizado}
            )
        return mensagens

    def _chamar(self, mensagens: list[dict[str, str]]) -> str:
        if urllib.parse.urlparse(self.base_url).scheme not in {"http", "https"}:
            raise ValueError("Esquema de URL inválido")
        pedido = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(
                {
                    "model": self.modelo,
                    "messages": mensagens,
                    "stream": False,
                    "options": {"temperature": 0.0, "seed": 42},
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(pedido, timeout=self.timeout_seconds) as resposta:  # nosec B310
            corpo: dict[str, Any] = json.loads(resposta.read().decode("utf-8"))
        conteudo = corpo["message"]["content"]
        if not isinstance(conteudo, str):
            raise ValueError("Conteúdo inválido")
        return conteudo

    def classificar(self, pergunta: str, resposta: str | None = None) -> DecisaoSegundaCamada:
        inicio = time.perf_counter()
        with trace_operation("guardrail_segunda_camada"):
            try:
                bloqueado, categorias = interpretar_saida(
                    self._chamar(self._mensagens(pergunta, resposta))
                )
                falha_fechada = False
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as erro:
                if self.modo == "avaliacao":
                    raise SegundaCamadaIndisponivel(type(erro).__name__) from erro
                bloqueado, categorias, falha_fechada = True, (), True
        decisao = DecisaoSegundaCamada(
            bloqueado=bloqueado,
            categorias=categorias,
            latencia_ms=round((time.perf_counter() - inicio) * 1000, 2),
            falha_fechada=falha_fechada,
        )
        logger.info(
            "decisao_segunda_camada",
            extra={
                "segunda_camada_bloqueado": decisao.bloqueado,
                "segunda_camada_categorias": list(decisao.categorias),
                "segunda_camada_latencia_ms": decisao.latencia_ms,
                "segunda_camada_falha_fechada": decisao.falha_fechada,
            },
        )
        return decisao


_AVALIACAO: ClassificadorLlamaGuard | None = None


def _classificador_avaliacao() -> ClassificadorLlamaGuard:
    global _AVALIACAO
    if _AVALIACAO is None:
        _AVALIACAO = ClassificadorLlamaGuard(modo="avaliacao")
    return _AVALIACAO


def deve_bloquear(pergunta: str) -> bool:
    """Alvo do guardrail_runner: só a segunda camada (modo avaliação: falha é erro)."""
    return _classificador_avaliacao().classificar(pergunta).bloqueado


def deve_bloquear_combinado(pergunta: str) -> bool:
    """Alvo do guardrail_runner: camadas 1 e 2 em série (bloqueia se qualquer uma bloquear)."""
    return deve_bloquear_camada_1(pergunta) or deve_bloquear(pergunta)
