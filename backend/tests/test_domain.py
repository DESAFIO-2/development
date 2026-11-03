from datetime import date, timedelta
from app.domain import (
    MedicationItemInput,
    PrescriptionAuditRequest,
    CoverageRoute,
    ComponenteSUS,
    MedicationCoverage,
    ItemRoteiroCidadao,
    CitizenGuidanceCard,
)


def test_criacao_prescription_audit_request() -> None:
    req = PrescriptionAuditRequest(
        itens=[
            MedicationItemInput(
                nome_digitado="Losartana 50mg",
                concentracao="50mg",
                forma_farmaceutica="comprimido",
            ),
            MedicationItemInput(
                nome_digitado="Dapagliflozina 10mg",
                concentracao="10mg",
            ),
        ],
        data_emissao=date.today(),
        regiao_administrativa="Ceilândia",
    )
    assert len(req.itens) == 2
    assert req.itens[0].nome_digitado == "Losartana 50mg"
    assert req.regiao_administrativa == "Ceilândia"


def test_criacao_medication_coverage() -> None:
    coverage = MedicationCoverage(
        dcb_principio_ativo="LOSARTANA POTASSICA",
        concentracao="50 MG",
        forma_farmaceutica="COMPRIMIDO",
        via_primaria=CoverageRoute.FARMACIA_POPULAR,
        disponivel_farmacia_popular=True,
        disponivel_ubs_df=True,
        exige_lme_alto_custo=False,
        validade_receita_dias=180,
        documentos_obrigatorios=["RG", "CPF", "Receita Médica"],
        fonte_oficial="Portaria GM/MS nº 6.324/2024",
    )
    assert coverage.via_primaria == CoverageRoute.FARMACIA_POPULAR
    assert coverage.disponivel_farmacia_popular is True
    assert coverage.validade_receita_dias == 180


def test_citizen_guidance_card_aviso_ato_medico() -> None:
    hoje = date.today()
    item = ItemRoteiroCidadao(
        medicamento_ou_exame="Losartana 50mg",
        principio_ativo_dcb="LOSARTANA POTASSICA",
        via_retirada=CoverageRoute.FARMACIA_POPULAR,
        local_sugerido="Drogarias privadas credenciadas ao Farmácia Popular no DF",
        o_que_levar=["Receita médica válida", "Documento oficial com foto", "CPF"],
        dias_validade_receita=180,
        data_limite_validade=hoje + timedelta(days=180),
        dias_restantes=180,
        alerta_vencimento_proximo=False,
        citacao_normativa="Portaria GM/MS nº 6.324/2024 (RENAME)",
    )
    card = CitizenGuidanceCard(
        regiao_administrativa="Ceilândia",
        itens_auditados=[item],
        resumo_acolhedor="Dona Helena, o seu remédio Losartana pode ser retirado 100% gratuito.",
    )
    assert card.sucesso is True
    assert "Não realizamos diagnósticos" in card.aviso_preservacao_ato_medico
    assert len(card.itens_auditados) == 1
