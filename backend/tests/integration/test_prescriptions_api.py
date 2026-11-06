from datetime import date

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_api_audit_prescription_sucesso() -> None:
    payload = {
        "itens": [
            {"nome_digitado": "Losartana Potássica 50mg"},
            {"nome_digitado": "Adalimumabe 40mg"},
        ],
        "data_emissao": str(date.today()),
        "regiao_administrativa": "Ceilândia",
    }
    response = client.post("/api/v1/prescriptions/audit", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["sucesso"] is True
    assert data["regiao_administrativa"] == "Ceilândia"
    assert len(data["itens"]) == 2

    # Item 1: Losartana -> FARMACIA_POPULAR
    assert data["itens"][0]["via_retirada"] == "FARMACIA_POPULAR"
    # Item 2: Adalimumabe -> FARMACIA_ALTO_CUSTO
    assert data["itens"][1]["via_retirada"] == "FARMACIA_ALTO_CUSTO"


def test_api_audit_prescription_bloqueio_clinico() -> None:
    payload = {
        "itens": [{"nome_digitado": "Dipirona 500mg"}],
        "pergunta_adicional": "Qual remédio é bom para dor nas costas?",
    }
    response = client.post("/api/v1/prescriptions/audit", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["sucesso"] is False
    assert len(data["itens"]) == 0
    assert (
        "Aviso Importante" in data["resumo_acolhedor"] or "Ato Médico" in data["resumo_acolhedor"]
    )


def test_api_autocomplete_medications() -> None:
    response = client.get("/api/v1/medications/autocomplete?q=losartana&limite=5")
    assert response.status_code == 200

    data = response.json()
    assert data["consulta"] == "losartana"
    assert data["total_encontrados"] > 0
    assert "LOSARTANA" in data["resultados"][0]["dcb_principio_ativo"]
