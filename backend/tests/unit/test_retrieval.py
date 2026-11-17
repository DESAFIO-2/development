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
    assert med.available_reme_df is True
    assert "36801" in med.notes


def test_tabular_matcher_equivalencia_milhar_e_sacubitril_escopada() -> None:
    repo = LocalCanonicalMedicationRepository()
    matcher = TabularDCBMatcher(repo.listar_todos())

    assert matcher.normalizar_concentracao("5.000 UI/0,25 mL") == "5000ui/0.25ml"
    assert matcher.normalizar_concentracao("0,125 mg") == "0.125mg"

    heparina = matcher.casar("heparina sódica", concentracao="5000 UI/0,25 mL")
    assert len(heparina) == 1
    assert heparina[0][1].concentration == "5.000 UI/0,25 mL"

    sacubitril = matcher.casar("sacubitril valsartana 97/103 mg", concentracao="97/103 mg")
    assert len(sacubitril) == 1
    assert sacubitril[0][1].concentration == "200 mg"
    assert sacubitril[0][1].dispensation_route == "ALTO_CUSTO_CEAF"


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


def test_tabular_matcher_nucleo_concentracao_intercalada_e_sugestao() -> None:
    repo = LocalCanonicalMedicationRepository()
    matcher = TabularDCBMatcher(repo.listar_todos())

    # Concentração com percentual documental entre parênteses ("5 mg/mL (0,5%)")
    timolol = matcher.casar("maleato de timolol", concentracao="5 mg/mL")
    assert len(timolol) >= 1
    assert "5 mg/mL" in timolol[0][1].concentration

    # Concentração com dispositivo/frasco ("0,1 mg/mL (frasco 2,5 mL)")
    desmo = matcher.casar("acetato de desmopressina", concentracao="0,1 mg/mL")
    assert len(desmo) >= 1

    # Associação em dose fixa intercalada no texto
    doses_interc = matcher.doses_no_texto("amoxicilina 500 mg + clavulanato de potássio 125 mg")
    assert doses_interc == {"500mg+125mg"}

    # Sugestão ortográfica para erro de 1 caractere sem selecionar silenciosamente
    assert matcher.casar("ibuprofneo 600 mg") == []
    sugestao = matcher.sugerir_correcao_ortografica("ibuprofneo 600 mg")
    assert sugestao is not None
    assert sugestao[0] == "ibuprofeno"
    assert "ibuprofeno" in sugestao[1]


def test_associacao_tres_componentes_preserva_pares_e_ordem() -> None:
    from dataclasses import replace

    import pytest

    base = LocalCanonicalMedicationRepository().listar_todos()[0]
    # Fixture de protocolo, não apresentação real nem evidência científica.
    med = replace(base, dcb_name="alfa + beta + gama", concentration="1 mg + 2 mg + 3 mg")
    matcher = TabularDCBMatcher([med])
    assert matcher.doses_no_texto("gama 3 mg + alfa 1 mg + beta 2 mg") == {"1mg+2mg+3mg"}
    for text in ("alfa 2 mg + beta 1 mg + gama 3 mg", "alfa 1 mg + beta 2 mg"):
        with pytest.raises(ValueError, match="não confirmada"):
            matcher.doses_no_texto(text)
        assert not matcher.casar(text)
