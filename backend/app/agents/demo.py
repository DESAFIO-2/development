"""Demo por API real em processo: python -m app.agents.demo [--input arquivo.json] [--strict]."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api.routes.agents import AgentRequestDTO
from app.application.agents import AgentRequest, GenerationFailure
from app.container import get_services
from app.main import app

DEMO_SCENARIOS: tuple[tuple[str, dict[str, Any]], ...] = (
    (
        "dona_helena_misto",
        {
            "itens": [
                {"nome_digitado": "losartana potássica 50 mg"},
                {"nome_digitado": "alendronato de sódio 70 mg"},
            ],
            "regiao_administrativa": "Ceilândia",
            "pergunta_adicional": "Onde fica a farmácia de alto custo em Ceilândia?",
        },
    ),
    (
        "lucas_ceaf_sisreg",
        {
            "itens": [
                {"nome_digitado": "Adalimumabe 40 mg"},
                {"nome_digitado": "Ecocardiograma Transtorácico"},
            ],
            "regiao_administrativa": "Asa Sul",
            "pergunta_adicional": "Quais documentos preciso para o Ecocardiograma?",
        },
    ),
    (
        "procuracao_fralda",
        {
            "regiao_administrativa": "Ceilândia",
            "pergunta_adicional": (
                "Quais documentos preciso para pegar fralda geriátrica com procuração?"
            ),
        },
    ),
    (
        "abstencao_nao_padronizado",
        {
            "itens": [{"nome_digitado": "tirzepatida 5 mg"}],
            "regiao_administrativa": "Gama",
        },
    ),
    (
        "bloqueio_clinico_emergencia",
        {
            "regiao_administrativa": "Taguatinga",
            "pergunta_adicional": (
                "Estou com dor no peito intensa e falta de ar, posso dobrar a losartana?"
            ),
        },
    ),
)


def _run_payload(client: TestClient, payload: dict[str, Any], *, strict: bool) -> dict[str, Any]:
    if strict:
        request = AgentRequest.model_validate(AgentRequestDTO.model_validate(payload).model_dump())
        response = get_services().agents.executar(request, strict=True)
        result: dict[str, Any] = json.loads(response.model_dump_json())
        return result
    http_response = client.post("/api/v1/agents/orchestrate", json=payload)
    http_response.raise_for_status()
    data: dict[str, Any] = http_response.json()
    return data


def main() -> int:
    # A saída redirecionada também é JSON UTF-8 no Windows (não CP1252).
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, help="Payload JSON UTF-8 (dados públicos ou sintéticos)"
    )
    parser.add_argument("--strict", action="store_true", help="Falha de geração retorna código 2")
    args = parser.parse_args()

    with TestClient(app) as client:
        try:
            if args.input:
                payload = json.loads(args.input.read_text(encoding="utf-8"))
                output: Any = _run_payload(client, payload, strict=args.strict)
            else:
                output = {
                    "cenarios": [
                        {
                            "cenario": name,
                            "resultado": _run_payload(client, payload, strict=args.strict),
                        }
                        for name, payload in DEMO_SCENARIOS
                    ]
                }
        except GenerationFailure as exc:
            print(exc.metadata.model_dump_json(indent=2))
            return 2
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
