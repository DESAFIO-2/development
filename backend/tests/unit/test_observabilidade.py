import json
import logging

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core.logs import FormatadorJson, request_id_var
from app.core.telemetry import trace_operation
from app.main import app

client = TestClient(app)


def test_toda_resposta_tem_request_id() -> None:
    response = client.get("/health")

    assert len(response.headers["X-Request-ID"]) == 32


def test_reaproveita_request_id_recebido() -> None:
    response = client.get("/health", headers={"X-Request-ID": "abc123"})

    assert response.headers["X-Request-ID"] == "abc123"


def test_registra_rota_status_e_duracao(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.http"):
        client.get("/health")

    # Campos extras do log ficam nos atributos do registro; vars() os expõe como dict.
    registro = next(vars(r) for r in caplog.records if r.name == "app.http")
    assert registro["rota"] == "/health"
    assert registro["status"] == 200
    assert registro["duracao_ms"] >= 0


def test_trace_operation_registra_duracao(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.telemetria"):
        with trace_operation("retrieval"):
            pass

    registro = next(vars(r) for r in caplog.records if r.name == "app.telemetria")
    assert registro["operacao"] == "retrieval"
    assert registro["duracao_ms"] >= 0


def test_formatador_gera_json_com_request_id() -> None:
    token = request_id_var.set("req-1")
    registro = logging.makeLogRecord(
        {"name": "app.teste", "levelname": "INFO", "msg": "oi", "status": 200}
    )

    linha = json.loads(FormatadorJson().format(registro))

    request_id_var.reset(token)
    assert linha["request_id"] == "req-1"
    assert linha["mensagem"] == "oi"
    assert linha["status"] == 200


def test_requisicao_gera_span_com_rota_e_request_id(spans: InMemorySpanExporter) -> None:
    client.get("/health", headers={"X-Request-ID": "abc123"})

    span_http = next(s for s in spans.get_finished_spans() if s.parent is None)
    atributos = span_http.attributes or {}
    assert atributos["http.route"] == "/health"
    assert atributos["app.request_id"] == "abc123"


def test_trace_operation_vira_span(spans: InMemorySpanExporter) -> None:
    with trace_operation("retrieval"):
        pass

    assert [s.name for s in spans.get_finished_spans()] == ["retrieval"]


def test_log_carrega_trace_id_dentro_de_um_span() -> None:
    registro = logging.makeLogRecord({"name": "app.teste", "levelname": "INFO", "msg": "oi"})

    with trace_operation("etapa"):
        linha = json.loads(FormatadorJson().format(registro))

    assert len(linha["trace_id"]) == 32


def test_log_json_carrega_a_decisao_anti_injection() -> None:
    registro = logging.makeLogRecord(
        {
            "name": "app.seguranca",
            "levelname": "INFO",
            "msg": "decisao_anti_injection",
            "seguranca_canal": "pdf",
            "seguranca_bloqueado": True,
            "seguranca_motivos": ["IGNORAR_INSTRUCOES"],
            "seguranca_versao_regras": "abc123",
        }
    )

    linha = json.loads(FormatadorJson().format(registro))

    assert linha["seguranca_canal"] == "pdf"
    assert linha["seguranca_bloqueado"] is True
    assert linha["seguranca_motivos"] == ["IGNORAR_INSTRUCOES"]
