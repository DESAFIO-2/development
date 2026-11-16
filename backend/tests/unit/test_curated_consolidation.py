"""Testes de integridade da consolidação multi-fonte (F01+F03+F04), chunks e MLflow."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from observability.mlflow_tracker import MLflowExperimentTracker

from app.infrastructure.persistence.repositories.canonical_medication_repository import (
    LocalCanonicalMedicationRepository,
)
from app.infrastructure.persistence.repositories.normative_chunk_repository import (
    LocalNormativeChunkRepository,
)
from app.ingestion.consolidate_curated_corpus import (
    RAIZ_REPO,
    chave_normalizada_concentracao,
    consolidar_catalogo_medicamentos,
    ler_bytes_lf,
    normalizar_concentracao,
    validate_evidencia_drift,
    validate_occurrence_drift,
)
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.tabular_matcher import TabularDCBMatcher


def test_normalizar_concentracao_unifica_f01_f03_f04() -> None:
    assert normalizar_concentracao("50mg*") == "50 mg"
    assert normalizar_concentracao("100ui/ml") == "100 UI/mL"
    assert normalizar_concentracao("0,02mg") == "0,02 mg"
    assert normalizar_concentracao("-") == "Padronizada"
    # Equivalência de separadores de milhar brasileiros entre F01 e F03
    assert chave_normalizada_concentracao("5.000 UI/0,25 mL") == chave_normalizada_concentracao(
        "5000 UI/0,25 mL"
    )
    assert chave_normalizada_concentracao("1.000 UI") == chave_normalizada_concentracao("1000 UI")
    assert chave_normalizada_concentracao("4.000 UI") == chave_normalizada_concentracao("4000 UI")
    assert chave_normalizada_concentracao("1.000 mg") == chave_normalizada_concentracao("1000 mg")
    assert chave_normalizada_concentracao("0,125 mg") != chave_normalizada_concentracao("125 mg")


def test_schema_drift_validation_curated_occurrences() -> None:
    caminho_occ = RAIZ_REPO / "data" / "staging" / "curated_occurrences_v9.jsonl"
    caminho_ev = RAIZ_REPO / "data" / "staging" / "curated_evidencias_v9.jsonl"
    occurrences = [
        json.loads(line) for line in ler_bytes_lf(caminho_occ).splitlines() if line.strip()
    ]
    evidencias = [
        json.loads(line) for line in ler_bytes_lf(caminho_ev).splitlines() if line.strip()
    ]

    report = validate_occurrence_drift(occurrences)
    assert report.is_valid is True
    assert report.total_records == 2114
    assert report.valid_records == 2114
    assert len(report.unexpected_fields) == 0
    assert Counter(row["item_type"] for row in occurrences) == {"medicine": 2085, "supply": 29}

    ev_report = validate_evidencia_drift(evidencias, occurrences)
    assert ev_report.is_valid is True
    assert ev_report.total_records == 2114
    assert ev_report.valid_records == 2114

    upstream = json.loads(ler_bytes_lf(RAIZ_REPO / "data/manifests/corpus_v9_source.json"))
    expected = upstream["staging_files_sha256"]
    assert (
        hashlib.sha256(ler_bytes_lf(caminho_occ)).hexdigest()
        == expected["curated_occurrences_v9.jsonl"]
    )
    assert (
        hashlib.sha256(ler_bytes_lf(caminho_ev)).hexdigest()
        == expected["curated_evidencias_v9.jsonl"]
    )
    excluido = upstream["excluded_occurrences"][0]["occurrence_id"]
    assert all(row["occurrence_id"] != excluido for row in occurrences)

    # Correções v6-v9 portadas de engenharia de dados (OCR, C-F03-003 e claritromicina)
    assert any(r["active_ingredient"] == "fenoximetilpenicilina potássica" for r in occurrences)
    assert any(
        r["occurrence_id"] == "occ-bc5acf38f4260802e843100c"
        and r["strength"] == "equivalente a 500 ou 600 mg de cálcio + colecalciferol 400 UI"
        for r in occurrences
    )

    canonico = RAIZ_REPO / "data/processed/medicamentos_sus_canonical.json"
    consolidado = consolidar_catalogo_medicamentos(occurrences)
    assert consolidado == json.loads(ler_bytes_lf(canonico))
    assert not validate_occurrence_drift([*occurrences, occurrences[0]]).is_valid
    assert not validate_evidencia_drift([*evidencias, evidencias[0]], occurrences).is_valid


def test_catalogo_consolidado_possui_cobertura_multifonte() -> None:
    caminho_canon = RAIZ_REPO / "data/processed/medicamentos_sus_canonical.json"
    catalogo_bruto = json.loads(caminho_canon.read_text(encoding="utf-8"))
    # Nenhum registro sintético occ == 0 ou item sem ocorrência comprovada
    assert all(len(item.get("occurrence_ids") or []) >= 1 for item in catalogo_bruto)
    assert all(
        item["medication_id"] != "MED-SACUBITRIL-VALSARTANA-97-103MG" for item in catalogo_bruto
    )

    repo = LocalCanonicalMedicationRepository()
    itens = repo.listar_todos()
    assert len(itens) >= 1750

    matcher = TabularDCBMatcher(itens)
    abacavir_hits = matcher.casar("abacavir 300 mg comprimido")
    assert len(abacavir_hits) > 0
    assert abacavir_hits[0][1].available_reme_df is True
    assert "Policlínica" in abacavir_hits[0][1].notes or "HUB" in abacavir_hits[0][1].notes

    fralda_hits = matcher.casar("fralda geriátrica")
    assert len(fralda_hits) > 0
    assert fralda_hits[0][1].dispensation_route == "FARMACIA_POPULAR"

    # Sacubitril/valsartana 97/103 mg -> 200 mg real com proveniência F01/F03
    sacubitril_hits = matcher.casar("sacubitril valsartana 97/103 mg", concentracao="97mg+103mg")
    assert len(sacubitril_hits) >= 1
    assert sacubitril_hits[0][1].concentration == "200 mg"
    assert sacubitril_hits[0][1].dispensation_route == "ALTO_CUSTO_CEAF"
    assert sacubitril_hits[0][1].requires_lme is True

    # Dapagliflozina 10 mg unificada F01+F03+F04 mantendo PFPB + alerta CEAF Cód. 36801
    dapa = next(item for item in catalogo_bruto if "dapagliflozina" in item["dcb_name"])
    assert len(dapa["occurrence_ids"]) == 3
    assert dapa["dispensation_route"] == "FARMACIA_POPULAR"
    assert dapa["available_reme_df"] is True
    assert "36801" in dapa["notes"]
    assert "LME" in dapa["notes"]

    # Claritromicina 500 mg comprimido unificada v9 (1 F01 + 3 F03 = 4 ocorrências)
    clari_500 = [
        item
        for item in catalogo_bruto
        if item["dcb_name"] == "claritromicina"
        and item["concentration"] == "500 mg"
        and item["pharmaceutical_form"] == "comprimido"
    ]
    assert len(clari_500) == 1
    assert len(clari_500[0]["occurrence_ids"]) == 4

    # Imunoglobulina anti-hepatite b sem resíduo "- -" e 1.000 UI == 1000 UI -> HOSPITALAR
    assert all("- -" not in item["dcb_name"] for item in catalogo_bruto)
    hep_1000 = [
        item
        for item in catalogo_bruto
        if item["dcb_name"] == "imunoglobulina humana anti-hepatite b"
        and chave_normalizada_concentracao(item["concentration"]) == "1000ui"
    ]
    assert len(hep_1000) == 1
    assert len(hep_1000[0]["occurrence_ids"]) == 2
    assert hep_1000[0]["dispensation_route"] == "HOSPITALAR"
    assert (
        matcher.casar("imunoglobulina humana anti-hepatite b 1000 UI", concentracao="1000 UI")[0][1]
        == matcher.casar("imunoglobulina humana anti-hepatite b 1.000 UI", concentracao="1.000 UI")[
            0
        ][1]
    )


def test_chunks_sincronizados_com_base_consolidada_e_manifesto() -> None:
    caminho_meds = RAIZ_REPO / "data" / "processed" / "medicamentos_sus_canonical.json"
    caminho_norm = RAIZ_REPO / "data" / "processed" / "normative_chunks.json"
    caminho_ev_chunks = RAIZ_REPO / "data" / "processed" / "evidence_chunks_v2.json"
    caminho_occ = RAIZ_REPO / "data" / "staging" / "curated_occurrences_v9.jsonl"
    caminho_ev = RAIZ_REPO / "data" / "staging" / "curated_evidencias_v9.jsonl"
    caminho_manifest = RAIZ_REPO / "data" / "manifests" / "manifest.json"

    assert not (RAIZ_REPO / "data" / "processed" / "unified_pdf_chunks.json").exists()
    assert not (RAIZ_REPO / "data" / "processed" / "medicamentos_sus_canonical_full.json").exists()

    manifest = json.loads(caminho_manifest.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == "2026.4.0"
    assert manifest["engineering_source"] == "corpus-consolidado-v9-aprovado-2026-11-12"

    assert (
        hashlib.sha256(ler_bytes_lf(caminho_meds)).hexdigest()
        == manifest["canonical_medications_sha256"]
    )
    assert (
        hashlib.sha256(ler_bytes_lf(caminho_norm)).hexdigest()
        == manifest["normative_chunks_sha256"]
    )
    assert (
        hashlib.sha256(ler_bytes_lf(caminho_ev_chunks)).hexdigest()
        == manifest["evidence_chunks_v2_sha256"]
    )
    assert (
        hashlib.sha256(ler_bytes_lf(caminho_occ)).hexdigest()
        == manifest["curated_occurrences_sha256"]
    )
    assert (
        hashlib.sha256(ler_bytes_lf(caminho_ev)).hexdigest()
        == manifest["curated_evidencias_sha256"]
    )

    norm_chunks = json.loads(caminho_norm.read_text(encoding="utf-8"))
    assert len(norm_chunks) == 20
    for nchk in norm_chunks:
        expected_sha = hashlib.sha256(str(nchk["text"]).encode("utf-8")).hexdigest()
        assert nchk["sha256"] == expected_sha

    ev_chunks = json.loads(caminho_ev_chunks.read_text(encoding="utf-8"))
    assert len(ev_chunks) == 2114
    assert len({str(c["chunk_id"]) for c in ev_chunks}) == 2114
    assert len({str(c["text"]) for c in ev_chunks}) == 2114
    assert all(str(c["literal_text"]).strip() for c in ev_chunks)


def test_hybrid_retriever_recupera_fontes_complementares_consolidada() -> None:
    med_repo = LocalCanonicalMedicationRepository()
    chunk_repo = LocalNormativeChunkRepository()
    retriever = HybridRetriever(med_repo.listar_todos(), chunk_repo.listar_todos())

    hits = retriever.search(
        "abacavir 300 mg e dolutegravir nas Policlínicas ou CEDIN no DF",
        top_k=3,
        min_score=0.18,
    )
    assert any(h.chunk_id == "CHK-COMP-SEC-001" for h in hits)


def test_mlflow_experiment_tracker_registra_linhagem(tmp_path: Path) -> None:
    manifest_dir = tmp_path / "data" / "manifests"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_bytes(
        (RAIZ_REPO / "data" / "manifests" / "manifest.json").read_bytes()
    )
    tracker = MLflowExperimentTracker(
        experiment_name="test-experiment",
        raiz_repo=tmp_path,
    )
    rec = tracker.registrar_execucao(
        run_name="unit_test_run",
        params={"rrf_k": 60, "min_score": 0.18},
        metrics={"hit_rate_at_3": 1.0, "mrr": 1.0},
    )
    assert rec.status == "FINISHED"
    assert rec.tags["manifest_version"] == "2026.4.0"
    assert len(rec.tags["evidence_chunks_v2_sha256"]) == 64
    assert rec.tags["evidence_chunks_v2_count"] == "2114"
    assert len(rec.tags["combined_sha256"]) == 64
