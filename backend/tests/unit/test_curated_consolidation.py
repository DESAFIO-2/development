"""Testes de integridade da consolidação multi-fonte (F01+F03+F04), chunks e MLflow."""

from __future__ import annotations

import hashlib
import json
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
    normalizar_concentracao,
    validate_occurrence_drift,
)
from app.retrieval.hybrid_retriever import HybridRetriever
from app.retrieval.tabular_matcher import TabularDCBMatcher


def test_normalizar_concentracao_unifica_f01_f03_f04() -> None:
    assert normalizar_concentracao("50mg*") == "50 mg"
    assert normalizar_concentracao("100ui/ml") == "100 UI/mL"
    assert normalizar_concentracao("0,02mg") == "0,02 mg"
    assert normalizar_concentracao("-") == "Padronizada"


def test_schema_drift_validation_curated_occurrences() -> None:
    caminho_occ = RAIZ_REPO / "data" / "staging" / "curated_occurrences_v1.jsonl"
    with caminho_occ.open(encoding="utf-8") as f:
        occurrences = [json.loads(line) for line in f if line.strip()]

    report = validate_occurrence_drift(occurrences)
    assert report.is_valid is True
    assert report.total_records == 2114
    assert report.valid_records == 2114
    assert len(report.unexpected_fields) == 0


def test_catalogo_consolidado_possui_cobertura_multifonte() -> None:
    repo = LocalCanonicalMedicationRepository()
    itens = repo.listar_todos()
    assert len(itens) >= 1750

    # Verifica presença de itens exclusivos da REME-DF (F03) e Farmácia Popular (F04)
    matcher = TabularDCBMatcher(itens)
    abacavir_hits = matcher.casar("abacavir 300 mg comprimido")
    assert len(abacavir_hits) > 0
    assert abacavir_hits[0][1].available_reme_df is True
    assert "Policlínica" in abacavir_hits[0][1].notes or "HUB" in abacavir_hits[0][1].notes

    fralda_hits = matcher.casar("fralda geriátrica")
    assert len(fralda_hits) > 0
    assert fralda_hits[0][1].dispensation_route == "FARMACIA_POPULAR"


def test_chunks_sincronizados_com_base_consolidada_e_manifesto() -> None:
    caminho_meds = RAIZ_REPO / "data" / "processed" / "medicamentos_sus_canonical.json"
    caminho_norm = RAIZ_REPO / "data" / "processed" / "normative_chunks.json"
    caminho_pdf = RAIZ_REPO / "data" / "processed" / "unified_pdf_chunks.json"
    caminho_manifest = RAIZ_REPO / "data" / "manifests" / "manifest.json"

    manifest = json.loads(caminho_manifest.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == "2026.3.0"

    assert (
        hashlib.sha256(caminho_meds.read_bytes()).hexdigest()
        == manifest["canonical_medications_sha256"]
    )
    assert (
        hashlib.sha256(caminho_norm.read_bytes()).hexdigest() == manifest["normative_chunks_sha256"]
    )
    assert (
        hashlib.sha256(caminho_pdf.read_bytes()).hexdigest()
        == manifest["unified_pdf_chunks_sha256"]
    )

    norm_chunks = json.loads(caminho_norm.read_text(encoding="utf-8"))
    assert len(norm_chunks) == 20
    for nchk in norm_chunks:
        expected_sha = hashlib.sha256(str(nchk["text"]).encode("utf-8")).hexdigest()
        assert nchk["sha256"] == expected_sha

    pdf_chunks = json.loads(caminho_pdf.read_text(encoding="utf-8"))
    assert len(pdf_chunks) == 70
    for pchk in pdf_chunks:
        assert pchk.get("review_status") == "approved"
        conteudo = str(pchk["content"])
        assert "24 medicamentos prioritários" not in conteudo
        assert pchk["sha256"] == hashlib.sha256(conteudo.encode("utf-8")).hexdigest()


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
    assert rec.tags["manifest_version"] == "2026.3.0"
    assert len(rec.tags["combined_sha256"]) == 64
