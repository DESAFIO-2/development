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


def test_api_audit_usa_apresentacao_selecionada_e_abstem_em_concentracao_desconhecida() -> None:
    response = client.post(
        "/api/v1/prescriptions/audit",
        json={
            "itens": [
                {
                    "nome_digitado": "Medicamento selecionado",
                    "principio_ativo_dcb": "losartana potássica",
                    "concentracao": "50mg",
                    "forma_farmaceutica": "comprimido",
                },
                {"nome_digitado": "Losartana 999mg"},
            ]
        },
    )
    assert response.status_code == 200
    selecionado, desconhecido = response.json()["itens"]
    assert selecionado["via_retirada"] == "FARMACIA_POPULAR"
    assert desconhecido["via_retirada"] == "NAO_PADRONIZADO"
    assert desconhecido["data_limite_validade"] is None


def test_api_audit_reconhece_rota_hospitalar_e_mascara_cpf_no_retorno() -> None:
    cpf = "123.456.789-00"
    response = client.post(
        "/api/v1/prescriptions/audit",
        json={"itens": [{"nome_digitado": f"abciximabe 2 mg/mL CPF {cpf}"}]},
    )
    assert response.status_code == 200
    assert response.json()["itens"][0]["via_retirada"] == "HOSPITALAR"
    assert cpf not in response.text


def test_api_audit_rejeita_data_futura_e_nome_em_branco() -> None:
    response = client.post(
        "/api/v1/prescriptions/audit",
        json={"itens": [{"nome_digitado": "  "}], "data_emissao": "9999-12-31"},
    )
    assert response.status_code == 422
    assert {tuple(erro["loc"]) for erro in response.json()["detail"]} == {
        ("body", "itens", 0, "nome_digitado"),
        ("body", "data_emissao"),
    }
