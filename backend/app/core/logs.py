"""Logs estruturados em JSON, com o ID da requisição em cada linha.

LGPD: nunca registre corpo de requisição, query string, CPF, CNS ou texto da receita.
Registre só metadados (rota, status, duração).
"""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

from opentelemetry import trace

# Guarda o ID da requisição atual. ContextVar isola o valor por requisição,
# mesmo com várias requisições rodando ao mesmo tempo (async).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

CAMPOS_EXTRAS = (
    "metodo",
    "rota",
    "status",
    "duracao_ms",
    "operacao",
    # Decisões da camada anti-injection (app.seguranca). Nunca o texto do cidadão.
    "seguranca_canal",
    "seguranca_bloqueado",
    "seguranca_motivos",
    "seguranca_versao_regras",
)


class FormatadorJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dados: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        # Se houver um trace do OpenTelemetry ativo, o log carrega o trace_id:
        # é ele que liga esta linha de log ao trace no Jaeger.
        contexto = trace.get_current_span().get_span_context()
        if contexto.is_valid:
            dados["trace_id"] = trace.format_trace_id(contexto.trace_id)
        for campo in CAMPOS_EXTRAS:
            if hasattr(record, campo):
                dados[campo] = getattr(record, campo)
        if record.exc_info:
            dados["erro"] = self.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False)


def configurar_logs(nivel: str = "INFO") -> None:
    """Liga a saída JSON para todos os loggers que começam com `app`."""
    handler = logging.StreamHandler()
    handler.setFormatter(FormatadorJson())
    logger_app = logging.getLogger("app")
    logger_app.handlers = [handler]
    logger_app.setLevel(nivel)
