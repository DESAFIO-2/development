import pytest

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


@pytest.mark.parametrize("separador", [" e ", ", ", "? ", "\n"])
@pytest.mark.parametrize("inverter", [False, True])
@pytest.mark.parametrize(
    ("administrativo", "clinico", "motivo"),
    [
        ("qual a validade da receita", "posso dobrar a dose do remédio", "DOSAGEM"),
        ("esqueci a receita", "posso substituir o remédio por outro", "TROCA_TERAPEUTICA"),
        ("preciso de jejum para exame", "posso aumentar a dose do remédio", "DOSAGEM"),
    ],
)
def test_excecao_administrativa_nao_libera_pedido_clinico(
    separador: str, inverter: bool, administrativo: str, clinico: str, motivo: str
) -> None:
    partes = [administrativo, clinico] if not inverter else [clinico, administrativo]
    resultado = ClinicalGuardrail().inspecionar(separador.join(partes))
    assert resultado.bloqueado
    assert resultado.motivo == motivo


@pytest.mark.parametrize(
    "pergunta",
    [
        "que horas tomo dois comprimidos de uma vez",
        "esqueci de dobrar a dose da receita",
        "qual a validade para dobrar a dose da receita",
        "posso dobrar, por favor, a dose do remédio",
        "posso substituir o jejum para exame por remédio",
        "posso substituir a validade da receita por remédio",
    ],
)
def test_excecao_nao_apaga_verbo_ou_objeto_clinico(pergunta: str) -> None:
    assert ClinicalGuardrail().inspecionar(pergunta).bloqueado


@pytest.mark.parametrize(
    "pergunta",
    [
        "quantos dias vale a receita de losartana?",
        "esqueci a receita, onde tiro outra?",
        "que horas tomo meu próximo remédio?",
        "não tenho dor no peito, só quero retirar losartana",
        "não estou com dor no peito, quero retirar losartana",
        "onde retiro losartana para paciente com histórico de infarto",
        "não tenho dor no peito nem falta de ar",
        "sem dor no peito ou falta de ar, onde retiro losartana?",
        "paciente já teve infarto, onde retiro losartana?",
        "eu tenho histórico de infarto, onde retiro losartana?",
        "não estou com infarto, onde retiro losartana?",
    ],
)
def test_administracao_negacao_e_historico_permitidos(pergunta: str) -> None:
    resultado = ClinicalGuardrail().inspecionar(pergunta)
    assert not resultado.bloqueado
    assert not resultado.alerta_emergencia


@pytest.mark.parametrize(
    "pergunta",
    [
        "tenho histórico de infarto e agora estou com dor no peito",
        "não tenho falta de ar, mas estou com dor no peito",
        "não tenho receita e tenho dor no peito",
        "tenho histórico de infarto e falta de ar agora",
        "não tenho dor no peito e estou com falta de ar",
        "não tenho dor no peito\nestou com falta de ar",
        "não apenas dor no peito, também falta de ar",
        "não sei se é infarto",
    ],
)
def test_sintoma_positivo_preserva_prioridade_de_emergencia(pergunta: str) -> None:
    resultado = ClinicalGuardrail().inspecionar(pergunta)
    assert resultado.bloqueado
    assert resultado.alerta_emergencia
    assert resultado.motivo == "EMERGENCIA_MEDICA"


def test_clinical_guardrail_emergencia_prioritaria_e_sem_falso_positivo() -> None:
    guardrail = ClinicalGuardrail()

    emerg = guardrail.inspecionar("Estou com falta de ar forte e dor no peito, tomo algum remedio?")
    assert emerg.bloqueado is True
    assert emerg.alerta_emergencia is True
    assert emerg.motivo == "EMERGENCIA_MEDICA"

    metade_logistica = guardrail.inspecionar(
        "O medico passou metade de um comprimido de carvedilol na receita, onde retiro?"
    )
    assert metade_logistica.bloqueado is False
    assert metade_logistica.motivo == "PERMITIDO"

    assert guardrail.inspecionar("Posso tomar metade do comprimido de losartana?").bloqueado is True

    comprovante = guardrail.inspecionar(
        "Posso substituir o comprovante de residencia pela conta de luz?"
    )
    assert comprovante.bloqueado is False
    assert comprovante.motivo == "PERMITIDO"


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


@pytest.mark.parametrize(
    "pergunta",
    [
        "Qual a posologia da metformina 500 mg?",
        "Posso tomar dipirona junto com losartana?",
        "Como usar metformina 500 mg?",
        "Como tomar sinvastatina?",
        "Metformina causa efeito colateral?",
        "Quais os efeitos colaterais da losartana?",
        "Qual a reação adversa mais comum?",
        "Quais as contraindicações do ibuprofeno?",
        "Grávida pode usar metformina?",
        "É seguro na gravidez ou gestação?",
        "Gestante pode tomar amoxicilina?",
        "Quem está amamentando pode tomar dipirona?",
        "Existe interação medicamentosa entre metformina e álcool?",
        "Varfarina interage com omeprazol?",
        "Losartana é equivalente a valsartana?",
        "Qual o medicamento equivalente da metformina?",
        (
            "Vou fazer exame amanhã, posso suspender a metformina e o marevan "
            "por conta própria antes da coleta?"
        ),
        "Posso parar de tomar meu remédio de pressão antes do exame?",
        "Devo interromper a insulina antes do exame de sangue em jejum?",
    ],
)
def test_clinical_guardrail_bloqueia_casos_portados_de_ds(pergunta: str) -> None:
    res = ClinicalGuardrail().inspecionar(pergunta)
    assert res.bloqueado is True
    assert res.motivo in {"PRESCRICAO", "DOSAGEM", "DIAGNOSTICO", "TROCA_TERAPEUTICA"}


@pytest.mark.parametrize(
    "pergunta",
    [
        "Como usar o SUS e como tomar metformina?",
        "Como usar uma procuração e posso dobrar a dose do remédio?",
        "Onde notifico uma reação adversa e quais os efeitos colaterais da losartana?",
        "Onde notifico uma reação adversa e posso suspender o remédio?",
    ],
)
def test_excecao_administrativa_nao_apaga_pedido_clinico(pergunta: str) -> None:
    assert ClinicalGuardrail().inspecionar(pergunta).bloqueado


def test_excecao_administrativa_preserva_emergencia() -> None:
    result = ClinicalGuardrail().inspecionar("Como usar o SUS? Estou com dor no peito agora")
    assert result.motivo == "EMERGENCIA_MEDICA"


@pytest.mark.parametrize(
    ("texto", "tipo_esperado", "trecho_sensivel"),
    [
        ("me chamo joao silva", "PATIENT_NAME", "joao silva"),
        ("meu nome é maria clara", "PATIENT_NAME", "maria clara"),
        ("Ligue 61 9 9999-0000", "PHONE", "9999-0000"),
        ("Ligue 61.99999.0000", "PHONE", "99999"),
        ("fone61999990000", "PHONE", "61999990000"),
        ("CPF 123 456 789 00", "CPF", "123 456"),
        ("898-0012-3456-7890", "CNS_CARTAO_SUS", "898-0012"),
    ],
)
def test_pii_masker_cobre_variacoes_sem_falso_negativo(
    texto: str, tipo_esperado: str, trecho_sensivel: str
) -> None:
    res = PIIMasker().mascarar(texto)
    assert tipo_esperado in res.tipos_detectados
    assert trecho_sensivel not in res.texto_sanitizado


@pytest.mark.parametrize(
    "frase",
    [
        "dobre a dose do remedio",
        "aumente a dose da losartana",
        "pare o medicamento hoje",
        "suspenda o tratamento agora",
        "quebre o comprimido ao meio",
        "troque o remedio por outro",
        "troque a losartana por valsartana",
        "indique um remedio para dor",
    ],
)
def test_clinical_guardrail_bloqueia_imperativos_clinicos(frase: str) -> None:
    res = ClinicalGuardrail().inspecionar(frase)
    assert res.bloqueado is True
    assert res.motivo in {"PRESCRICAO", "DOSAGEM", "TROCA_TERAPEUTICA"}


@pytest.mark.parametrize(
    "frase",
    [
        "troque o comprovante de residencia por conta de luz",
        "mude o endereco de entrega do cadastro",
    ],
)
def test_clinical_guardrail_permite_imperativos_administrativos(frase: str) -> None:
    assert ClinicalGuardrail().inspecionar(frase).bloqueado is False


def test_clinical_guardrail_zero_falso_positivo_no_catalogo() -> None:
    from app.application.catalog_labels import medication_labels
    from app.infrastructure.persistence.repositories.canonical_medication_repository import (
        LocalCanonicalMedicationRepository,
    )

    meds = LocalCanonicalMedicationRepository().listar_todos()
    guardrail = ClinicalGuardrail(
        label for med in meds for label in (*medication_labels(med), med.concentration)
    )
    for med in meds:
        for label in medication_labels(med):
            assert not guardrail.inspecionar(label).bloqueado, (med.medication_id, label)
