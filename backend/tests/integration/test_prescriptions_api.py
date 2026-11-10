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


def test_api_auditoria_v5_distingue_apresentacoes_f04_e_canal_f03() -> None:
    response = client.post(
        "/api/v1/prescriptions/audit",
        json={
            "itens": [
                {
                    "nome_digitado": "benzilpenicilina benzatina",
                    "principio_ativo_dcb": "benzilpenicilina benzatina",
                    "concentracao": "1.200.000 UI",
                    "forma_farmaceutica": "pó para suspensão injetável",
                },
                {"nome_digitado": "acetato de medroxiprogesterona 10mg"},
                {"nome_digitado": "acetato de medroxiprogesterona 150mg"},
                {"nome_digitado": "abacavir 300mg"},
                {"nome_digitado": "fralda geriátrica"},
            ]
        },
    )
    assert response.status_code == 200
    benzil, oral, elenco, abacavir, insumo = response.json()["itens"]
    assert benzil["via_retirada"] == oral["via_retirada"] == "UBS_REME_DF"
    assert elenco["via_retirada"] == "FARMACIA_POPULAR"
    assert elenco["citacao_normativa"] == "PFPB_2026 (p. 1)"
    assert "Policlínica" in abacavir["local_sugerido"]
    assert "CEDIN" in abacavir["local_sugerido"]
    assert insumo["via_retirada"] == "FARMACIA_POPULAR"
    assert insumo["dias_validade_receita"] is None
