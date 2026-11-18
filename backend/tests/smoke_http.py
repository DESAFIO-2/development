"""Smoke HTTP contra um servidor já iniciado (host ou container), sem TestClient.

Da raiz: uv run --project backend python backend/tests/smoke_http.py --base-url URL
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any


def requisitar(base_url: str, rota: str, payload: dict[str, Any] | None = None) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        base_url.rstrip("/") + rota,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        assert response.status == 200, response.status
        return json.load(response)


def executar(base_url: str) -> None:
    prazo = time.monotonic() + 30
    while True:
        try:
            requisitar(base_url, "/health")
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if time.monotonic() >= prazo:
                raise
            time.sleep(0.5)
    resultado = requisitar(base_url, "/api/v1/medications/autocomplete?q=losartana&limite=1")
    assert resultado["total_encontrados"] == 1
    casos = [
        ("onde retiro losartana?", True, False),
        ("qual a validade da receita e posso dobrar a dose do remédio", False, False),
        ("esqueci a receita e posso substituir o remédio por outro", False, False),
        ("não estou com dor no peito, quero retirar losartana", True, False),
        ("onde retiro losartana para paciente com histórico de infarto", True, False),
        ("não tenho receita e tenho dor no peito", False, True),
        ("tenho histórico de infarto e falta de ar agora", False, True),
    ]
    for pergunta, permitido, emergencia in casos:
        resposta = requisitar(
            base_url,
            "/api/v1/prescriptions/audit",
            {
                "itens": [{"nome_digitado": "losartana potássica 50 mg"}],
                "pergunta_adicional": pergunta,
            },
        )
        assert resposta["sucesso"] is permitido, pergunta
        if permitido:
            assert resposta["itens"][0]["via_retirada"] == "FARMACIA_POPULAR", pergunta
        else:
            assert resposta["itens"] == [], pergunta
        assert ("ALERTA DE EMERGÊNCIA" in resposta["resumo_acolhedor"]) is emergencia, pergunta
    agents = requisitar(
        base_url,
        "/api/v1/agents/orchestrate",
        {
            "itens": [
                {"nome_digitado": "losartana 50 mg"},
                {"nome_digitado": "Endoscopia Digestiva Alta"},
            ],
        },
    )
    assert agents["card"]["sucesso"]
    assert agents["primary_route"] == "ROTEIRO_MISTO_MULTICANAL"
    assert len(agents["agent_trace"]) == 4
    assert agents["citacoes"]
    blocked = requisitar(
        base_url,
        "/api/v1/agents/orchestrate",
        {
            "pergunta_adicional": "Tenho dor no peito e falta de ar agora",
        },
    )
    assert blocked["primary_route"] == "BLOQUEADO"
    assert "192" in blocked["card"]["resumo_acolhedor"]
    print(f"HTTP smoke aprovado: health, autocomplete, {len(casos)} auditorias e 2 grafos.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    executar(parser.parse_args().base_url)
