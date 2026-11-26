"""Coleta reproduzível da Semana 4 (modelo local Ollama).

Nunca fabrica qualidade de LLM nem troca falha real por saída determinística.
Executar via ambiente backend:
  cd backend && uv run python ../evals/runners/semana4_comparativo.py --run-dir ../evals/reports/s4
"""

# ruff: noqa: E402
from __future__ import annotations

import argparse
import json
import math
import platform
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "backend"))

from app.agents.demo import DEMO_SCENARIOS
from app.agents.orchestrator import LangGraphOrchestrator
from app.application.agents import AgentRequest, GenerationFailure
from app.application.ports import GenerationResultDTO, GeneratorPort, RetrievalHitDTO
from app.container import ServiceContainer, build_orchestrator, build_services
from app.infrastructure.llm.generator import PROMPT_VERSION_AGENTS, OllamaRESTGeneratorAdapter
from evals.runners.artifacts import (
    atomic_json,
    atomic_text,
    bind_manifest,
    digest,
    read_json,
    source_hashes,
)
from evals.runners.local_preflight import ollama_identity

DEFAULT_MODELS = ("qwen3.5:4b",)
RNF04_LATENCY_LIMIT_MS = 8000.0
DEFAULT_NUM_CTX = 4096
DEFAULT_NUM_PREDICT = 280


@dataclass(frozen=True)
class Semana4CaseResult:
    model: str
    case_id: str
    payload: dict[str, Any]
    primary_route: str
    generation_status: str
    error_code: str | None
    latency_ms: float | None
    wall_ms: float
    provider: str | None
    response_text: str | None
    summary_text: str
    context_chunk_ids: list[str]
    agent_trace: list[dict[str, Any]]
    scientific_status: str


class SyntheticSmokeGenerator(GeneratorPort):
    """Fixture explícita somente para --synthetic-smoke; nunca representa evidência científica."""

    prompt_version: str = PROMPT_VERSION_AGENTS

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def generate(
        self,
        question: str,
        evidences: tuple[RetrievalHitDTO, ...] = (),
        *,
        rag_mode: bool | None = None,
    ) -> GenerationResultDTO:
        return GenerationResultDTO(
            text="Consulte os trechos e documentos oficiais apresentados no roteiro.",
            provider="synthetic_smoke",
            model_name=self.model_name,
            grounded=bool(evidences) if rag_mode is None else rag_mode,
            latency_ms=1.0,
            execution_kind="llm",
        )


def _checkpoint_path(
    run_dir: Path,
    model: str,
    case_id: str,
    payload: dict[str, Any],
    *,
    synthetic_smoke: bool,
    model_digest: str,
    prompt_version: str = PROMPT_VERSION_AGENTS,
    num_ctx: int = 8192,
    num_predict: int = 450,
) -> Path:
    key = digest(
        {
            "model": model,
            "model_digest": model_digest,
            "case_id": case_id,
            "payload": payload,
            "synthetic_smoke": synthetic_smoke,
            "prompt_version": prompt_version,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
        }
    )
    return run_dir / "checkpoints" / f"{model.replace(':', '_')}_{case_id}_{key[:10]}.json"


def _run_case(
    *,
    orchestrator: LangGraphOrchestrator,
    model: str,
    case_id: str,
    payload: dict[str, Any],
    synthetic_smoke: bool,
) -> Semana4CaseResult:
    request = AgentRequest.model_validate(payload)
    started = time.perf_counter()
    scientific_status = (
        "SMOKE_SINTETICO_NAO_E_EVIDENCIA"
        if synthetic_smoke
        else "COLETA_CONCLUIDA_REVISAO_PENDENTE"
    )
    try:
        response = orchestrator.executar(request, strict=True)
        wall_ms = round((time.perf_counter() - started) * 1000, 2)
        return Semana4CaseResult(
            model=model,
            case_id=case_id,
            payload=payload,
            primary_route=response.primary_route,
            generation_status=response.generation.status,
            error_code=response.generation.error_code,
            latency_ms=response.generation.latency_ms,
            wall_ms=wall_ms,
            provider=response.generation.provider,
            response_text=response.resposta_adicional,
            summary_text=response.card.resumo_acolhedor,
            context_chunk_ids=list(response.generation.context_chunk_ids),
            agent_trace=[item.model_dump() for item in response.agent_trace],
            scientific_status=scientific_status,
        )
    except GenerationFailure as exc:
        wall_ms = round((time.perf_counter() - started) * 1000, 2)
        return Semana4CaseResult(
            model=model,
            case_id=case_id,
            payload=payload,
            primary_route="FALHA_ESTRICTA",
            generation_status=exc.metadata.status,
            error_code=exc.metadata.error_code,
            latency_ms=exc.metadata.latency_ms,
            wall_ms=wall_ms,
            provider=exc.metadata.provider,
            response_text=None,
            summary_text="",
            context_chunk_ids=list(exc.metadata.context_chunk_ids),
            agent_trace=[],
            scientific_status=scientific_status,
        )


def _summarize_model(
    model: str,
    items: list[dict[str, Any]],
    *,
    warmup_ms: float | None = None,
    warmup_error: str | None = None,
) -> dict[str, Any]:
    latencies = [float(it["wall_ms"]) for it in items]
    gen_latencies = [float(it["latency_ms"]) for it in items if it.get("latency_ms") is not None]
    failures = [
        it
        for it in items
        if it["generation_status"] in {"FALHA_PROVEDOR", "SAIDA_REJEITADA", "CONTEXTO_REJEITADO"}
    ]
    mediana_wall = round(statistics.median(latencies), 2) if latencies else None
    sorted_lat = sorted(latencies)
    p95_wall = (
        round(sorted_lat[max(0, math.ceil(0.95 * len(sorted_lat)) - 1)], 2) if sorted_lat else None
    )
    return {
        "model": model,
        "warmup_ms": warmup_ms,
        "warmup_error": warmup_error,
        "casos_executados": len(items),
        "gerados": sum(1 for it in items if it["generation_status"] == "GERADO"),
        "abstencoes": sum(1 for it in items if it["generation_status"] == "ABSTENCAO"),
        "bloqueados": sum(1 for it in items if it["generation_status"] == "BLOQUEADO"),
        "falhas_ou_rejeicoes": len(failures),
        "mediana_wall_ms": mediana_wall,
        "p95_wall_ms": p95_wall,
        "mediana_geracao_ms": round(statistics.median(gen_latencies), 2) if gen_latencies else None,
        "dentro_meta_rnf04_8s": (p95_wall is not None and p95_wall <= RNF04_LATENCY_LIMIT_MS),
    }


def _unload_ollama_model(base_url: str, model: str, timeout_seconds: float) -> None:
    try:
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/generate",
            data=json.dumps({"model": model, "keep_alive": 0}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=min(timeout_seconds, 10.0)) as resp:  # nosec B310
            resp.read()
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return


def run_comparison(
    *,
    run_dir: Path,
    models: list[str],
    base_url: str,
    timeout_seconds: float,
    limit: int | None = None,
    synthetic_smoke: bool = False,
    status_only: bool = False,
    services: ServiceContainer | None = None,
    prompt_version: str = PROMPT_VERSION_AGENTS,
    warmup: bool = False,
    keep_alive: str | None = None,
    num_ctx: int = DEFAULT_NUM_CTX,
    num_predict: int = DEFAULT_NUM_PREDICT,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    scenarios = list(DEMO_SCENARIOS[:limit] if limit is not None else DEMO_SCENARIOS)

    if status_only:
        report: dict[str, Any] = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "prompt_version": prompt_version,
            "base_url": base_url,
            "models": models,
            "casos_planejados": len(scenarios),
            "execucao_real": False,
            "status_cientifico": "NAO_AVALIADO",
            "motivo": "Coleta local no MacBook/Ollama ainda não executada neste host.",
            "resultados_por_modelo": {},
        }
        atomic_json(run_dir / "resultado.json", report)
        atomic_text(run_dir / "resultado.md", _render_markdown(report))
        return report

    identity: dict[str, Any] = (
        {"provider": "synthetic_smoke", "models": list(models)}
        if synthetic_smoke
        else ollama_identity(base_url, models)
    )
    bind_manifest(
        run_dir,
        {
            "synthetic_smoke": synthetic_smoke,
            "prompt_version": prompt_version,
            "warmup": warmup,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "base_url": base_url,
            "models": list(models),
            "cases": [[case_id, payload] for case_id, payload in scenarios],
            "ollama_identity": identity,
            "source_sha256": source_hashes(RAIZ),
        },
    )
    resolved_services = services or build_services()
    per_model: dict[str, list[dict[str, Any]]] = {}
    warmup_stats: dict[str, tuple[float | None, str | None]] = {}

    for model in models:
        model_digest = (
            "synthetic_smoke"
            if synthetic_smoke
            else str(identity.get("models", {}).get(model, {}).get("digest", ""))
        )
        generator: GeneratorPort = (
            SyntheticSmokeGenerator(model)
            if synthetic_smoke
            else OllamaRESTGeneratorAdapter(
                base_url=base_url,
                model_name=model,
                timeout_seconds=timeout_seconds,
                prompt_version=prompt_version,
                skip_input_guardrail=True,
                keep_alive=keep_alive or ("10m" if warmup else None),
                num_ctx=num_ctx,
                num_predict=num_predict,
            )
        )
        checkpoints = [
            _checkpoint_path(
                run_dir,
                model,
                case_id,
                payload,
                synthetic_smoke=synthetic_smoke,
                model_digest=model_digest,
                prompt_version=prompt_version,
                num_ctx=num_ctx,
                num_predict=num_predict,
            )
            for case_id, payload in scenarios
        ]
        needs_execution = any(not ckpt.exists() for ckpt in checkpoints)
        w_ms: float | None = None
        w_err: str | None = None
        if (
            warmup
            and needs_execution
            and not synthetic_smoke
            and isinstance(generator, OllamaRESTGeneratorAdapter)
        ):
            try:
                w_ms = generator.warmup()
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                w_err = type(exc).__name__
        warmup_stats[model] = (w_ms, w_err)

        orchestrator = build_orchestrator(resolved_services, generator)
        entries: list[dict[str, Any]] = []
        for (case_id, payload), ckpt in zip(scenarios, checkpoints, strict=True):
            cached = read_json(ckpt) if ckpt.exists() else None
            if cached is not None:
                entries.append(cached)
                continue
            item = asdict(
                _run_case(
                    orchestrator=orchestrator,
                    model=model,
                    case_id=case_id,
                    payload=payload,
                    synthetic_smoke=synthetic_smoke,
                )
            )
            if item["generation_status"] != "FALHA_PROVEDOR":
                atomic_json(ckpt, item)
            entries.append(item)
        per_model[model] = entries
        if warmup and needs_execution and not synthetic_smoke and len(models) > 1:
            _unload_ollama_model(base_url, model, timeout_seconds)

    has_provider_failure = any(
        item["generation_status"] == "FALHA_PROVEDOR"
        for items in per_model.values()
        for item in items
    )
    if synthetic_smoke:
        scientific_status = "SMOKE_SINTETICO_NAO_E_EVIDENCIA"
    elif has_provider_failure:
        scientific_status = "COLETA_COM_FALHAS_PROVEDOR"
    else:
        scientific_status = "COLETA_CONCLUIDA_REVISAO_PENDENTE"
    report = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "host": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "prompt_version": prompt_version,
        "warmup": warmup,
        "base_url": base_url,
        "ollama_identity": identity,
        "models": models,
        "casos_planejados": len(scenarios),
        "execucao_real": not synthetic_smoke,
        "status_cientifico": scientific_status,
        "resumos": {
            model: _summarize_model(
                model,
                items,
                warmup_ms=warmup_stats.get(model, (None, None))[0],
                warmup_error=warmup_stats.get(model, (None, None))[1],
            )
            for model, items in per_model.items()
        },
        "resultados_por_modelo": per_model,
    }
    atomic_json(run_dir / "resultado.json", report)
    atomic_text(run_dir / "resultado.md", _render_markdown(report))
    return report


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Comparativo Multiagente Semana 4 (Ollama Local)",
        "",
        f"- **Status Científico:** `{report['status_cientifico']}`",
        f"- **Execução Real:** `{report['execucao_real']}`",
        f"- **Prompt Version:** `{report['prompt_version']}`",
        f"- **Warmup Explícito:** `{bool(report.get('warmup'))}`",
        f"- **Casos Planejados:** {report['casos_planejados']}",
        "",
    ]
    resumos: dict[str, Any] = report.get("resumos", {})
    if not resumos:
        lines.append(report.get("motivo", "Execução ainda não realizada."))
        lines.append("")
        return "\n".join(lines)
    lines.extend(
        [
            "| Modelo | Casos | Gerados | Abstenções | Bloqueios | Falhas | "
            "Warmup (ms) | Mediana (ms) | p95 (ms) | RNF04 <= 8s |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for model, stats in resumos.items():
        w = stats.get("warmup_ms")
        w_str = "N/A" if w is None else str(w)
        lines.append(
            f"| `{model}` | {stats['casos_executados']} | {stats['gerados']} | "
            f"{stats['abstencoes']} | {stats['bloqueados']} | {stats['falhas_ou_rejeicoes']} | "
            f"{w_str} | {stats['mediana_wall_ms']} | {stats['p95_wall_ms']} | "
            f"{stats['dentro_meta_rnf04_8s']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=RAIZ / "evals/reports/semana4_comparativo",
    )
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--prompt-version", default=PROMPT_VERSION_AGENTS)
    parser.add_argument(
        "--warmup",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Pré-aquece cada modelo antes dos casos e registra warmup_ms separadamente.",
    )
    parser.add_argument("--keep-alive", default="10m")
    parser.add_argument("--num-ctx", type=int, default=DEFAULT_NUM_CTX)
    parser.add_argument("--num-predict", type=int, default=DEFAULT_NUM_PREDICT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pilot", action="store_true", help="Executa somente os 2 primeiros casos")
    parser.add_argument(
        "--synthetic-smoke",
        action="store_true",
        help="Exercita somente o encanamento sem LLM real (não gera evidência científica)",
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Registra relatório estrutural NAO_AVALIADO sem chamar o Ollama",
    )
    args = parser.parse_args()
    limit = 2 if args.pilot else args.limit
    report = run_comparison(
        run_dir=args.run_dir,
        models=list(args.models),
        base_url=args.base_url,
        timeout_seconds=args.timeout,
        limit=limit,
        synthetic_smoke=args.synthetic_smoke,
        status_only=args.status_only,
        prompt_version=args.prompt_version,
        warmup=args.warmup,
        keep_alive=args.keep_alive,
        num_ctx=args.num_ctx,
        num_predict=args.num_predict,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
