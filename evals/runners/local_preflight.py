"""Identifica o servidor e os pesos locais antes de congelar uma execução."""

from __future__ import annotations

import json
import urllib.request
from typing import Any


def ollama_identity(base_url: str, models: list[str]) -> dict[str, Any]:
    base = base_url.rstrip("/").removesuffix("/v1")

    def get(path: str) -> Any:
        with urllib.request.urlopen(f"{base}{path}", timeout=15) as response:  # nosec B310
            return json.load(response)

    version = get("/api/version")["version"]
    installed = get("/api/tags")["models"]
    selected = {}
    for model in models:
        found = next((m for m in installed if m["name"] in {model, model + ":latest"}), None)
        if found is None or not found.get("digest"):
            raise ValueError(f"Modelo local não instalado: {model}. Execute ollama pull {model}")
        selected[model] = {k: found.get(k) for k in ("name", "digest", "size", "details")}
    return {"version": version, "models": selected}
