"""Rastreador de Experimentos Científicos e Linhagem de Dados (MLflow & JSON Lineage).

Implementa o rastreamento padronizado de experimentos de avaliação do RAG Híbrido e
comparativos LLM x RAG, registrando hiperparâmetros (`rrf_k`, `min_score`, `top_k`),
métricas de recuperação (`hit_rate_at_3`, `recall_at_3`, `mrr`, `acuracia_roteamento`,
`taxa_bloqueio_clinico`, `acuracia_abstencao`) e hashes SHA-256 do manifesto de dados
(`data/manifests/manifest.json`).

Compatível com servidor/pacote `mlflow` quando instalado no ambiente e com persistência
local determinística em `evals/reports/mlflow_runs/` (Ponytail Zero-Bloat).
"""

from __future__ import annotations

import hashlib
import importlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ_PADRAO = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ExperimentRunRecord:
    """Registro auditável de uma execução experimental estilo MLflow."""

    run_id: str
    experiment_name: str
    run_name: str
    status: str
    started_at_utc: str
    finished_at_utc: str
    params: dict[str, str]
    metrics: dict[str, float]
    tags: dict[str, str]
    artifact_uri: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MLflowExperimentTracker:
    """Adaptador de observabilidade experimental com suporte a MLflow e JSON local."""

    def __init__(
        self,
        experiment_name: str = "sus-cidadao-rag-benchmarks",
        raiz_repo: Path = RAIZ_PADRAO,
    ) -> None:
        self.experiment_name = experiment_name
        self.raiz_repo = raiz_repo
        self.pasta_runs = self.raiz_repo / "evals" / "reports" / "mlflow_runs"
        self.caminho_manifesto = self.raiz_repo / "data" / "manifests" / "manifest.json"

    def carregar_linhagem_manifesto(self) -> dict[str, str]:
        """Extrai versão e hashes SHA-256 do manifesto de dados consolidados."""
        if not self.caminho_manifesto.exists():
            return {"manifest_version": "unknown", "combined_sha256": "none"}

        dados: dict[str, Any] = json.loads(self.caminho_manifesto.read_text(encoding="utf-8"))
        counts = dados.get("record_counts") or {}
        return {
            "manifest_version": str(dados.get("manifest_version", "unknown")),
            "engineering_source": str(dados.get("engineering_source", "unknown")),
            "canonical_medications_sha256": str(dados.get("canonical_medications_sha256", "")),
            "normative_chunks_sha256": str(dados.get("normative_chunks_sha256", "")),
            "unified_pdf_chunks_sha256": str(dados.get("unified_pdf_chunks_sha256", "")),
            "combined_sha256": str(dados.get("combined_sha256", "")),
            "canonical_medications_count": str(counts.get("canonical_medications", 0)),
            "normative_chunks_count": str(counts.get("normative_chunks", 0)),
        }

    def registrar_execucao(
        self,
        run_name: str,
        params: dict[str, Any],
        metrics: dict[str, float],
        dataset_path: Path | None = None,
        extra_tags: dict[str, str] | None = None,
    ) -> ExperimentRunRecord:
        """Registra parâmetros, métricas e linhagem no MLflow (se ativo) e em disco."""
        inicio = datetime.now(UTC).isoformat()
        run_id = uuid.uuid4().hex
        linhagem = self.carregar_linhagem_manifesto()

        tags: dict[str, str] = {
            "project": "sus-cidadao-navegasus",
            "architecture": "clean-architecture-ponytail",
            **linhagem,
        }
        if dataset_path and dataset_path.exists():
            tags["dataset_file"] = dataset_path.name
            tags["dataset_sha256"] = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
        if extra_tags:
            tags.update(extra_tags)

        params_str = {str(k): str(v) for k, v in params.items()}
        metrics_float = {str(k): float(v) for k, v in metrics.items()}

        # Tenta logar no pacote mlflow caso esteja instalado no ambiente
        self._log_to_native_mlflow_if_available(
            run_name=run_name,
            params=params_str,
            metrics=metrics_float,
            tags=tags,
        )

        self.pasta_runs.mkdir(parents=True, exist_ok=True)
        destino_run = self.pasta_runs / f"run_{run_id[:12]}.json"
        fim = datetime.now(UTC).isoformat()

        uri_str = (
            str(destino_run.relative_to(self.raiz_repo))
            if destino_run.is_relative_to(self.raiz_repo)
            else str(destino_run)
        )
        registro = ExperimentRunRecord(
            run_id=run_id,
            experiment_name=self.experiment_name,
            run_name=run_name,
            status="FINISHED",
            started_at_utc=inicio,
            finished_at_utc=fim,
            params=params_str,
            metrics=metrics_float,
            tags=tags,
            artifact_uri=uri_str,
        )

        conteudo_json = json.dumps(registro.to_dict(), ensure_ascii=False, indent=2) + "\n"
        destino_run.write_text(conteudo_json, encoding="utf-8")

        ultimo_run = self.raiz_repo / "evals" / "reports" / "mlflow_latest_run.json"
        ultimo_run.write_text(conteudo_json, encoding="utf-8")
        return registro

    def _log_to_native_mlflow_if_available(
        self,
        run_name: str,
        params: dict[str, str],
        metrics: dict[str, float],
        tags: dict[str, str],
    ) -> None:
        """Envia telemetria ao MLflow nativo se a biblioteca estiver instalada."""
        try:
            mlflow_mod: Any = importlib.import_module("mlflow")
        except ModuleNotFoundError:
            return

        tracking_dir = self.raiz_repo / "evals" / "reports" / "mlruns"
        mlflow_mod.set_tracking_uri(tracking_dir.as_uri())
        mlflow_mod.set_experiment(self.experiment_name)
        with mlflow_mod.start_run(run_name=run_name):
            mlflow_mod.log_params(params)
            mlflow_mod.log_metrics(metrics)
            mlflow_mod.set_tags(tags)


__all__ = ["ExperimentRunRecord", "MLflowExperimentTracker"]
