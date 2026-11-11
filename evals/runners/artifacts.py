"""Persistência atômica e identidade de experimentos; nenhum acesso a modelos."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def bind_manifest(directory: Path, identity: dict[str, Any]) -> None:
    path = directory / "manifesto.json"
    if path.exists():
        if read_json(path) != identity:
            raise ValueError("Experimento incompatível: código, dados ou configuração mudaram")
    else:
        atomic_json(path, identity)


def source_hashes(root: Path) -> dict[str, str]:
    files = [
        *sorted((root / "backend/app").rglob("*.py")),
        *sorted((root / "evals/runners").glob("*.py")),
        root / "backend/uv.lock",
        root / "evals/uv.lock",
        root / "data/processed/medicamentos_sus_canonical.json",
        root / "data/processed/normative_chunks.json",
    ]
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(
            p.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        for p in files
    }
