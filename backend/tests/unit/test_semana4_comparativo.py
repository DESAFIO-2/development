"""Testes unitários do runner reproduzível da Semana 4 (sem rede externa)."""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest
from evals.runners.semana4_comparativo import run_comparison

from app.container import ServiceContainer, build_services


@pytest.fixture(scope="module")
def services() -> ServiceContainer:
    return build_services()


def test_semana4_comparativo_status_only_is_nao_avaliado(
    tmp_path: Path, services: ServiceContainer
) -> None:
    report = run_comparison(
        run_dir=tmp_path,
        models=["qwen2.5:7b", "qwen2.5:14b"],
        base_url="http://localhost:11434",
        timeout_seconds=10.0,
        status_only=True,
        services=services,
    )
    assert report["status_cientifico"] == "NAO_AVALIADO"
    assert report["execucao_real"] is False
    assert (tmp_path / "resultado.json").exists()
    assert (tmp_path / "resultado.md").exists()


def test_semana4_comparativo_synthetic_smoke_and_checkpoint_resume(
    tmp_path: Path, services: ServiceContainer
) -> None:
    first = run_comparison(
        run_dir=tmp_path,
        models=["qwen2.5:7b"],
        base_url="http://localhost:11434",
        timeout_seconds=10.0,
        limit=2,
        synthetic_smoke=True,
        services=services,
    )
    assert first["status_cientifico"] == "SMOKE_SINTETICO_NAO_E_EVIDENCIA"
    assert first["execucao_real"] is False
    summary = first["resumos"]["qwen2.5:7b"]
    assert summary["casos_executados"] == 2
    assert summary["gerados"] == 2

    with patch(
        "evals.runners.semana4_comparativo._run_case",
        side_effect=AssertionError("checkpoint deveria evitar nova execução"),
    ):
        resumed = run_comparison(
            run_dir=tmp_path,
            models=["qwen2.5:7b"],
            base_url="http://localhost:11434",
            timeout_seconds=10.0,
            limit=2,
            synthetic_smoke=True,
            services=services,
        )
    assert resumed["resumos"]["qwen2.5:7b"]["casos_executados"] == 2


def test_semana4_comparativo_records_provider_failure_without_fallback(
    tmp_path: Path, services: ServiceContainer
) -> None:
    identity = {
        "version": "0.6.0",
        "models": {"qwen2.5:7b": {"name": "qwen2.5:7b", "digest": "abc123", "size": 1}},
    }
    with (
        patch("evals.runners.semana4_comparativo.ollama_identity", return_value=identity),
        patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ),
    ):
        report = run_comparison(
            run_dir=tmp_path,
            models=["qwen2.5:7b"],
            base_url="http://localhost:11434",
            timeout_seconds=5.0,
            limit=1,
            services=services,
        )
    assert report["status_cientifico"] == "COLETA_COM_FALHAS_PROVEDOR"
    caso = report["resultados_por_modelo"]["qwen2.5:7b"][0]
    assert caso["generation_status"] == "FALHA_PROVEDOR"
    assert caso["primary_route"] == "FALHA_ESTRICTA"
    saved = json.loads((tmp_path / "resultado.json").read_text(encoding="utf-8"))
    assert saved["resumos"]["qwen2.5:7b"]["falhas_ou_rejeicoes"] == 1
    assert not list((tmp_path / "checkpoints").glob("*.json"))


def test_semana4_comparativo_p95_outlier_and_manifest_isolation(
    tmp_path: Path, services: ServiceContainer
) -> None:
    from evals.runners.semana4_comparativo import _summarize_model

    summary = _summarize_model(
        "qwen2.5:7b",
        [
            {"generation_status": "GERADO", "wall_ms": 100.0, "latency_ms": 50.0},
            {"generation_status": "GERADO", "wall_ms": 9000.0, "latency_ms": 8900.0},
        ],
    )
    assert summary["p95_wall_ms"] == 9000.0
    assert summary["dentro_meta_rnf04_8s"] is False

    run_comparison(
        run_dir=tmp_path,
        models=["qwen2.5:7b"],
        base_url="http://localhost:11434",
        timeout_seconds=10.0,
        limit=1,
        synthetic_smoke=True,
        services=services,
    )
    identity = {
        "version": "0.6.0",
        "models": {"qwen2.5:7b": {"name": "qwen2.5:7b", "digest": "abc123", "size": 1}},
    }
    with (
        patch("evals.runners.semana4_comparativo.ollama_identity", return_value=identity),
        pytest.raises(ValueError, match="Experimento incompatível"),
    ):
        run_comparison(
            run_dir=tmp_path,
            models=["qwen2.5:7b"],
            base_url="http://localhost:11434",
            timeout_seconds=10.0,
            limit=1,
            synthetic_smoke=False,
            services=services,
        )


def test_ollama_adapter_warmup_and_think_false_for_qwen35() -> None:
    from io import BytesIO

    from app.infrastructure.llm.generator import OllamaRESTGeneratorAdapter

    captured_payloads: list[dict[str, object]] = []

    class _FakeResp(BytesIO):
        def __enter__(self) -> _FakeResp:
            return self

        def __exit__(self, *args: object) -> None:
            self.close()

    def fake_urlopen(req: object, timeout: float = 0.0) -> _FakeResp:
        data = json.loads(req.data.decode("utf-8"))  # type: ignore[attr-defined]
        captured_payloads.append(data)
        return _FakeResp(json.dumps({"response": "ok"}).encode("utf-8"))

    adapter_qwen35 = OllamaRESTGeneratorAdapter(
        base_url="http://localhost:11434",
        model_name="qwen3.5:4b",
        keep_alive="15m",
        num_ctx=4096,
        num_predict=280,
    )
    assert adapter_qwen35.think is False
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        warmup_ms = adapter_qwen35.warmup()
        req = adapter_qwen35._request("teste")
        gen_payload = json.loads(req.data.decode("utf-8"))  # type: ignore[union-attr]
    assert warmup_ms >= 0.0
    assert captured_payloads[0]["think"] is False
    assert captured_payloads[0]["keep_alive"] == "15m"
    assert gen_payload["think"] is False
    assert gen_payload["keep_alive"] == "15m"
    assert gen_payload["options"]["num_ctx"] == 4096

    adapter_qwen25 = OllamaRESTGeneratorAdapter(model_name="qwen2.5:7b")
    assert adapter_qwen25.think is None
    req25 = adapter_qwen25._request("teste")
    assert "think" not in json.loads(req25.data.decode("utf-8"))  # type: ignore[union-attr]
