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
