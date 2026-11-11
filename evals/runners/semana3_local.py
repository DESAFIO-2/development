"""Orquestra coleta/avaliação; não confunde auditoria pendente com falha técnica."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--dataset", default="evals/datasets/golden_set_v2_consolidado.jsonl")
    parser.add_argument("--model", default="semana3-qwen14")
    parser.add_argument("--embedding-model", default="bge-m3")
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    directory = args.run_dir.resolve()
    started = time.perf_counter()
    collect = [
        "uv",
        "run",
        "--project",
        "backend",
        "python",
        "evals/runners/comparar_semana3.py",
        "--provider",
        "ollama",
        "--model",
        args.model,
        "--base-url",
        args.base_url,
        "--timeout",
        "180",
        "--dataset",
        args.dataset,
        "--run-dir",
        str(directory),
    ]
    if args.pilot:
        collect += ["--limit", "2"]
    result = subprocess.run(collect, cwd=ROOT, check=False)
    if result.returncode:
        return result.returncode
    evaluate = [
        "uv",
        "run",
        "--project",
        "evals",
        "python",
        "evals/runners/avaliar_ragas_oficial.py",
        "--coleta-dir",
        str(directory),
        "--evaluator-model",
        args.model,
        "--embedding-model",
        args.embedding_model,
        "--base-url",
        args.base_url.rstrip("/") + "/v1",
    ]
    result = subprocess.run(evaluate, cwd=ROOT, check=False)
    if result.returncode not in (0, 2, 3):
        return result.returncode
    report = json.loads((directory / "avaliacao_ragas.json").read_text(encoding="utf-8"))
    if not report["avaliacao_ragas_completa"]:
        return 1
    print(f"Inferência concluída em {time.perf_counter() - started:.1f}s em {platform.platform()}.")
    print(f"Status científico: {report['status_entregavel']}. Arquivos: {directory}")
    print("Próximo passo: revisão humana e --consolidate-only. Nenhuma superioridade é presumida.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
