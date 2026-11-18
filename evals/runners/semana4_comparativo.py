"""Coleta reproduzível da Semana 4 (Qwen2.5 7B vs 14B no Ollama).

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
from app.application.use_cases.audit_prescription import AuditPrescriptionUseCase
from app.container import ServiceContainer, build_services
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

DEFAULT_MODELS = ("qwen2.5:7b", "qwen2.5:14b")
RNF04_LATENCY_LIMIT_MS = 8000.0


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
) -> Path:
    key = digest(
        {
            "model": model,
            "model_digest": model_digest,
            "case_id": case_id,
            "payload": payload,
            "synthetic_smoke": synthetic_smoke,
            "prompt_version": PROMPT_VERSION_AGENTS,
        }
    )
    return run_dir / "checkpoints" / f"{model.replace(':', '_')}_{case_id}_{key[:10]}.json"


def _build_orchestrator(
    services: ServiceContainer,
    generator: GeneratorPort | None,
) -> LangGraphOrchestrator:
    auditor = AuditPrescriptionUseCase(
        medication_repo=services.medication_repo,
        retriever=services.hybrid_retriever,
        guardrail=services.guardrail,
        tabular_matcher=services.tabular_matcher,
        evidence_repo=services.evidence_chunk_repo,
    )
    return LangGraphOrchestrator(
        auditor=auditor,
        guardrail=services.guardrail,
        retriever=services.hybrid_retriever,
        generator=generator,
        public_context=services.public_context,
    )


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


def _summarize_model(model: str, items: list[dict[str, Any]]) -> dict[str, Any]:
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
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    scenarios = list(DEMO_SCENARIOS[:limit] if limit is not None else DEMO_SCENARIOS)

    if status_only:
        report: dict[str, Any] = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "prompt_version": PROMPT_VERSION_AGENTS,
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
            "prompt_version": PROMPT_VERSION_AGENTS,
            "base_url": base_url,
            "models": list(models),
            "cases": [[case_id, payload] for case_id, payload in scenarios],
            "ollama_identity": identity,
            "source_sha256": source_hashes(RAIZ),
        },
    )
    resolved_services = services or build_services()
    per_model: dict[str, list[dict[str, Any]]] = {}

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
                prompt_version=PROMPT_VERSION_AGENTS,
            )
        )
        orchestrator = _build_orchestrator(resolved_services, generator)
        entries: list[dict[str, Any]] = []
        for case_id, payload in scenarios:
            ckpt = _checkpoint_path(
                run_dir,
                model,
                case_id,
                payload,
                synthetic_smoke=synthetic_smoke,
                model_digest=model_digest,
            )
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
        "prompt_version": PROMPT_VERSION_AGENTS,
        "base_url": base_url,
        "ollama_identity": identity,
        "models": models,
        "casos_planejados": len(scenarios),
        "execucao_real": not synthetic_smoke,
        "status_cientifico": scientific_status,
        "resumos": {model: _summarize_model(model, items) for model, items in per_model.items()},
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
            "Mediana (ms) | p95 (ms) | RNF04 <= 8s |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for model, stats in resumos.items():
        lines.append(
            f"| `{model}` | {stats['casos_executados']} | {stats['gerados']} | "
            f"{stats['abstencoes']} | {stats['bloqueados']} | {stats['falhas_ou_rejeicoes']} | "
            f"{stats['mediana_wall_ms']} | {stats['p95_wall_ms']} | "
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
    parser.add_argument("--timeout", type=float, default=30.0)
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
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
