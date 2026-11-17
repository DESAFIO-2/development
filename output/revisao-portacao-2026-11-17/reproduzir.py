"""Reproduções de revisão; não representam benchmark científico nem aprovação."""
import json
import logging
from fastapi.testclient import TestClient
from app.main import app
from app.guardrails.clinical import ClinicalGuardrail

logging.disable(logging.CRITICAL)
results = []
cases = [
    ({"nome_digitado": "clavulanato de potássio 500 mg + amoxicilina 125 mg"}, "NAO_PADRONIZADO"),
    ({"nome_digitado": "maleato de timolol", "concentracao": "5 mg/mL (99%)"}, "NAO_PADRONIZADO"),
    ({"nome_digitado": "acetato de desmopressina", "concentracao": "0,1 mg/mL (frasco 999 mL)"}, "NAO_PADRONIZADO"),
    ({"nome_digitado": "dipropionato de beclometasona 50 mcg"}, "FARMACIA_POPULAR"),
    ({"nome_digitado": "dipropionato de beclometasona 250 mcg"}, "FARMACIA_POPULAR"),
    ({"nome_digitado": "sacubitril valsartana 97/103 mg", "concentracao": "200 mg"}, "FARMACIA_ALTO_CUSTO"),
]
with TestClient(app) as client:
    for item, expected in cases:
        response = client.post("/api/v1/prescriptions/audit", json={"itens": [item]})
        actual = response.json()["itens"][0]["via_retirada"]
        results.append({"input": item, "expected": expected, "actual": actual, "ok": actual == expected})
for question in ["Como usar a Farmácia Popular?", "Como usar o SUS?", "Como usar uma procuração para retirar medicamentos?", "Onde notifico uma reação adversa?"]:
    actual = ClinicalGuardrail().inspecionar(question).bloqueado
    results.append({"input": question, "expected_blocked": False, "actual_blocked": actual, "ok": not actual})
print(json.dumps(results, ensure_ascii=False, indent=2))
