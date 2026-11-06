from datetime import date

from app.application.use_cases.audit_prescription import AuditPrescriptionUseCase
from app.domain.medication import CoverageRoute
from app.domain.prescription import MedicationItemInput, PrescriptionAuditRequest
from app.infrastructure.persistence.repositories.canonical_medication_repository import (
    LocalCanonicalMedicationRepository,
)
from app.infrastructure.persistence.repositories.normative_chunk_repository import (
    LocalNormativeChunkRepository,
)
from app.retrieval.hybrid_retriever import HybridRetriever


def _make_use_case() -> AuditPrescriptionUseCase:
    med_repo = LocalCanonicalMedicationRepository()
    chunk_repo = LocalNormativeChunkRepository()
    retriever = HybridRetriever(med_repo.listar_todos(), chunk_repo.listar_todos())
    return AuditPrescriptionUseCase(medication_repo=med_repo, retriever=retriever)


def test_audit_prescricao_persona_dona_helena() -> None:
    use_case = _make_use_case()
    req = PrescriptionAuditRequest(
        itens=[
            MedicationItemInput(nome_digitado="Losartana Potássica 50mg"),
            MedicationItemInput(nome_digitado="Cloridrato de Metformina 850mg"),
            MedicationItemInput(nome_digitado="Dapagliflozina 10mg"),
        ],
        data_emissao=date.today(),
        regiao_administrativa="Ceilândia",
    )

    card = use_case.executar(req)
    assert card.sucesso is True
    assert card.solicitou_automedicacao is False
    assert len(card.itens_auditados) == 3

    # Losartana -> Farmácia Popular
    losartana = card.itens_auditados[0]
    assert losartana.via_retirada == CoverageRoute.FARMACIA_POPULAR
    assert "Farmácia Popular" in losartana.local_sugerido

    # Metformina -> Farmácia Popular
    metformina = card.itens_auditados[1]
    assert metformina.via_retirada == CoverageRoute.FARMACIA_POPULAR

    # Dapagliflozina -> Farmácia Popular
    dapa = card.itens_auditados[2]
    assert dapa.via_retirada == CoverageRoute.FARMACIA_POPULAR


def test_audit_prescricao_persona_lucas_alto_custo() -> None:
    use_case = _make_use_case()
    req = PrescriptionAuditRequest(
        itens=[MedicationItemInput(nome_digitado="Adalimumabe 40mg")],
        data_emissao=date.today(),
        regiao_administrativa="Taguatinga Sul",
    )

    card = use_case.executar(req)
    assert card.sucesso is True
    assert len(card.itens_auditados) == 1

    item = card.itens_auditados[0]
    assert item.via_retirada == CoverageRoute.FARMACIA_ALTO_CUSTO
    assert "Alto Custo" in item.local_sugerido
    assert any("LME" in doc for doc in item.o_que_levar)


def test_audit_prescricao_bloqueio_clinico() -> None:
    use_case = _make_use_case()
    req = PrescriptionAuditRequest(
        itens=[MedicationItemInput(nome_digitado="Losartana 50mg")],
        pergunta_adicional="Posso dobrar a dose hoje porque minha pressão subiu?",
    )

    card = use_case.executar(req)
    assert card.sucesso is False
    assert card.solicitou_automedicacao is True
    assert len(card.itens_auditados) == 0
    assert (
        "Preservação do Ato Médico" in card.resumo_acolhedor
        or "ALERTA DE EMERGÊNCIA" in card.resumo_acolhedor
    )
