from app.application.ports import GuardrailPort
from app.guardrails import LocalGuardrailAdapter
from app.guardrails.clinical import ClinicalGuardrail, deve_bloquear
from app.guardrails.pii import PIIMasker, mascarar_pii


def test_clinical_guardrail_bloqueia_automedicacao() -> None:
    guardrail = ClinicalGuardrail()

    res1 = guardrail.inspecionar("Posso dobrar a dose da Losartana?")
    assert res1.bloqueado is True
    assert res1.motivo == "DOSAGEM"

    res2 = guardrail.inspecionar("Qual remédio é bom para gripe forte?")
    assert res2.bloqueado is True
    assert res2.motivo == "PRESCRICAO"

    res3 = guardrail.inspecionar("Onde retiro Losartana de graça no DF?")
    assert res3.bloqueado is False
    assert res3.motivo == "PERMITIDO"


def test_deve_bloquear_funcao_alvo() -> None:
    assert deve_bloquear("Posso tomar dois comprimidos hoje?") is True
    assert deve_bloquear("Como renovar receita de remédio controlado?") is False


def test_pii_masker_sanitiza_dados_pessoais() -> None:
    masker = PIIMasker()
    texto = (
        "Paciente: Maria Helena Souza, CPF: 123.456.789-00, CNS: 898 0012 3456 7890, "
        "telefone 61 98888-7777, email: helena@email.com. Receita de Losartana 50mg."
    )
    resultado = masker.mascarar(texto)

    assert "123.456.789-00" not in resultado.texto_sanitizado
    assert "[CPF_MASCARADO_LGPD]" in resultado.texto_sanitizado
    assert "[CNS_MASCARADO_LGPD]" in resultado.texto_sanitizado
    assert "[TELEFONE_MASCARADO_LGPD]" in resultado.texto_sanitizado
    assert "[EMAIL_MASCARADO_LGPD]" in resultado.texto_sanitizado
    assert "Losartana 50mg" in resultado.texto_sanitizado


def test_mascarar_pii_atalho() -> None:
    limpo = mascarar_pii("Meu CPF é 000.111.222-33")
    assert "000.111.222-33" not in limpo


def test_pii_masker_cobre_rg_crm_cid_cep_endereco_e_nome_livre() -> None:
    masker = PIIMasker()
    texto = (
        "Me chamo João Carlos Silva, RG 12.345.678-9, CRM-DF 12345, CID-10 I10, "
        "CEP 72215-000, Quadra QNM 18 Conjunto A Casa 4, moro em Taguatinga Sul "
        "e busco Losartana 50mg na Farmácia Popular."
    )
    res = masker.mascarar(texto)
    for sensivel in ("João Carlos Silva", "12.345.678-9", "12345", "I10", "72215-000", "QNM 18"):
        assert sensivel not in res.texto_sanitizado
    assert "Taguatinga Sul" in res.texto_sanitizado
    assert "Losartana 50mg" in res.texto_sanitizado
    assert "Farmácia Popular" in res.texto_sanitizado
    assert {"PATIENT_NAME", "RG", "CRM", "CID10", "CEP", "ADDRESS"}.issubset(
        set(res.tipos_detectados)
    )


def test_local_guardrail_adapter_implementa_guardrail_port() -> None:
    adapter = LocalGuardrailAdapter()
    assert isinstance(adapter, GuardrailPort)
    assert adapter.verificar_ato_medico("Dá pra partir o comprimido de metformina?").bloqueado
    assert (
        "123.456.789-00"
        not in adapter.desidentificar_dados_pessoais("CPF 123.456.789-00").texto_sanitizado
    )
