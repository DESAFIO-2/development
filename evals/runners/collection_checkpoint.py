"""Checkpoint por braço: respostas recebidas nunca são regeneradas na retomada."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from app.application.ports import GenerationResultDTO, GeneratorPort, RetrievalHitDTO
from evals.runners.artifacts import atomic_json, digest, read_json


class CheckpointGenerator(GeneratorPort):
    def __init__(self, generator: GeneratorPort, directory: Path) -> None:
        self.generator = generator
        self.directory = directory
        self.case_id = "single"

    def generate(
        self,
        question: str,
        evidences: tuple[RetrievalHitDTO, ...] = (),
        *,
        rag_mode: bool | None = None,
    ) -> GenerationResultDTO:
        request = {
            "case_id": self.case_id,
            "question": question,
            "evidences": [asdict(e) for e in evidences],
            "rag_mode": rag_mode,
        }
        path = self.directory / f"{digest(request)}.json"
        if path.exists():
            saved = read_json(path)
            if saved["request"] != request or digest(saved["result"]) != saved["result_sha256"]:
                raise ValueError("Checkpoint de geração corrompido")
            return GenerationResultDTO(**saved["result"])
        result = self.generator.generate(question, evidences, rag_mode=rag_mode)
        atomic_json(
            path,
            {"request": request, "result": asdict(result), "result_sha256": digest(asdict(result))},
        )
        return result
