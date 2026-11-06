from app.infrastructure.persistence.repositories.canonical_medication_repository import (
    LocalCanonicalMedicationRepository,
)
from app.infrastructure.persistence.repositories.normative_chunk_repository import (
    LocalNormativeChunkRepository,
)
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.tabular_matcher import TabularDCBMatcher


def test_tabular_matcher_losartana() -> None:
    repo = LocalCanonicalMedicationRepository()
    matcher = TabularDCBMatcher(repo.listar_todos())

    matches = matcher.casar("Losartana Potássica 50mg comprimido")
    assert len(matches) > 0
    score, med = matches[0]
    assert "losartana" in med.dcb_name
    assert score >= 0.90
    assert med.available_pfpb is True


def test_tabular_matcher_adalimumabe_alto_custo() -> None:
    repo = LocalCanonicalMedicationRepository()
    matcher = TabularDCBMatcher(repo.listar_todos())

    matches = matcher.casar("Adalimumabe 40mg")
    assert len(matches) > 0
    _, med = matches[0]
    assert "adalimumabe" in med.dcb_name
    assert med.requires_lme is True
    assert med.dispensation_route == "ALTO_CUSTO_CEAF"


def test_tabular_matcher_dapagliflozina_farmacia_popular() -> None:
    repo = LocalCanonicalMedicationRepository()
    matcher = TabularDCBMatcher(repo.listar_todos())

    matches = matcher.casar("Dapagliflozina 10mg")
    assert len(matches) > 0
    _, med = matches[0]
    assert "dapagliflozina" in med.dcb_name
    assert med.dispensation_route == "FARMACIA_POPULAR"


def test_hybrid_retriever_recupera_norma_e_abstem_fora_de_elenco() -> None:
    med_repo = LocalCanonicalMedicationRepository()
    chunk_repo = LocalNormativeChunkRepository()
    retriever = HybridRetriever(med_repo.listar_todos(), chunk_repo.listar_todos())

    # Caso Positivo: Losartana deve retornar chunks normativos
    hits = retriever.search("losartana potássica 50 mg onde retirar no DF", top_k=3, min_score=0.18)
    assert len(hits) > 0
    assert hits[0].score >= 0.18

    # Caso Negativo / Abstenção: Termo sem cobertura pública no elenco
    hits_neg = retriever.search(
        "semaglutida estética ozempic para emagrecer", top_k=3, min_score=0.18
    )
    assert len(hits_neg) == 0
