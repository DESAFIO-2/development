"""Decisão idempotente para o PR de snapshots; não publica nem altera GitHub."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Literal

SNAPSHOTS = (
    "data/processed/ceaf_live_stock.json",
    "data/processed/df_pharmacies_geolocated.json",
)


def material(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in payload.items() if key != "synced_at_utc"}
        for payload in payloads
    ]


def decide(
    base: list[dict[str, Any]],
    latest: list[dict[str, Any]],
    proposed: list[dict[str, Any]] | None,
) -> Literal["close", "noop", "update"]:
    """A volta à base invalida o PR; coleta idêntica ao PR preserva sua revisão."""
    if material(latest) == material(base):
        return "close"
    if proposed is not None and material(latest) == material(proposed):
        return "noop"
    return "update"


def read_ref(ref: str) -> list[dict[str, Any]]:
    return [
        json.loads(subprocess.check_output(["git", "show", f"{ref}:{path}"], text=True))
        for path in SNAPSHOTS
    ]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposed-ref")
    args = parser.parse_args()
    print(
        decide(
            read_ref("HEAD"),
            [json.loads(Path(path).read_text(encoding="utf-8")) for path in SNAPSHOTS],
            read_ref(args.proposed_ref) if args.proposed_ref else None,
        )
    )
