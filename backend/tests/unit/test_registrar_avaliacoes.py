"""Registro das avaliações no rastreador: extração dos artefatos e idempotência."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import patch

from observability.mlflow_tracker import MLflowExperimentTracker
from observability.registrar_avaliacoes import (
    registrar,
    registros_guardrail,
    registros_quatro_bracos,
    registros_ragas,
    registros_seguranca,
    registros_semana4,
    registros_semana4_avaliacao,
)


def _seguranca() -> dict[str, Any]:
    def braco(status: str, clinico: int) -> dict[str, Any]:
        return {
            "status": status,
            "falhas": [] if status == "APROVADO" else ["SEG-CLI-01"],
            "invalidos": [],
            "injecao": {"aprovados": 4, "total": 4},
            "pii": {"aprovados": 4, "total": 4},
            "clinico": {"aprovados": clinico, "total": 4},
            "injecao_indireta": {"aprovados": 2, "total": 2},
        }

    return {
        "dataset": "seguranca_variantes_v1.jsonl",
        "tipo_execucao": "COLETA_REAL",
        "executado_em": "2026-11-17T12:00:00+00:00",
        "manifesto": {"model": "semana3-qwen14"},
        "bracos": {"B_llm_com_rag": braco("ELIMINADO", 3), "C_rag_sem_llm": braco("APROVADO", 4)},
    }


def test_seguranca_vira_uma_execucao_por_braco() -> None:
    registros = {r.run_name: r for r in registros_seguranca(_seguranca())}
    assert set(registros) == {"seguranca_B_llm_com_rag", "seguranca_C_rag_sem_llm"}
    b = registros["seguranca_B_llm_com_rag"]
    assert b.metrics["clinico_taxa"] == 0.75
    assert b.metrics["injecao_indireta_taxa"] == 1.0  # categoria da suíte v2
    assert b.metrics["aprovado_seguranca"] == 0.0 and b.metrics["falhas"] == 1.0
    assert b.params["model"] == "semana3-qwen14" and b.tags["status"] == "ELIMINADO"
    assert registros["seguranca_C_rag_sem_llm"].metrics["aprovado_seguranca"] == 1.0


def test_ragas_ignora_metrica_nula_e_nomeia_pela_variante() -> None:
    relatorio = {
        "dataset": "golden_set_v2_consolidado.jsonl",
        "variante": "blindado",
        "avaliacao_ragas_completa": True,
        "ragas_oficial": {
            "evaluator_model": "semana3-qwen14",
            "sem_rag": {"faithfulness": None, "answer_relevancy": 0.29},
            "com_rag": {"faithfulness": 0.87, "context_precision": 1.0},
        },
        "metricas": {"com_rag": {"rota_correta_heuristica": 1.0}},
    }
    [registro] = registros_ragas(relatorio)
    assert registro.run_name == "ragas_blindado"
    assert "sem_rag_faithfulness" not in registro.metrics
    assert registro.metrics["com_rag_faithfulness"] == 0.87
    assert registro.metrics["com_rag_rota_correta_heuristica"] == 1.0
    assert registro.metrics["avaliacao_ragas_completa"] == 1.0


def test_quatro_bracos_marca_o_escolhido_e_nao_inventa_rota() -> None:
    relatorio = {
        "dataset": "golden_set_v2_consolidado.jsonl",
        "escolha": {"braco": "C"},
        "bracos": {
            "B": {"acerto_rota": 1.0, "metas_atingidas": 2, "seguranca": "ELIMINADO"},
            "C": {"acerto_rota": None, "metas_atingidas": 0, "seguranca": "APROVADO"},
        },
    }
    registros = {r.run_name: r for r in registros_quatro_bracos(relatorio)}
    c = registros["quatro_bracos_C"]
    assert c.metrics["escolhido"] == 1.0 and "acerto_rota" not in c.metrics
    assert registros["quatro_bracos_B"].metrics["escolhido"] == 0.0


def test_guardrail_leva_recall_e_falso_bloqueio() -> None:
    [registro] = registros_guardrail(
        {
            "alvo": "app.guardrails.clinical:deve_bloquear",
            "dataset": "guardrail_holdout_cego_v1.jsonl",
            "recall_bloqueio": 1.0,
            "taxa_falso_bloqueio": 0.125,
            "deviam_permitir": 8,
            "bloqueados_indevidamente": 1,
        }
    )
    assert registro.run_name == "guardrail_guardrail_holdout_cego_v1_clinical.deve_bloquear"
    assert registro.metrics["taxa_falso_bloqueio"] == 0.125


def test_registrar_o_mesmo_artefato_duas_vezes_nao_duplica(tmp_path: Path) -> None:
    artefato = tmp_path / "seguranca.json"
    artefato.write_text(json.dumps(_seguranca()), encoding="utf-8")
    tracker = MLflowExperimentTracker(raiz_repo=tmp_path)

    assert registrar(tracker, "seguranca", artefato, "teste") == (2, 0)
    assert registrar(tracker, "seguranca", artefato, "teste") == (0, 2)

    gravados = [json.loads(p.read_text()) for p in tracker.pasta_runs.glob("run_*.json")]
    assert len(gravados) == 2
    assert {g["tags"]["rotulo"] for g in gravados} == {"teste"}


def test_semana4_um_registro_por_modelo_com_meta_de_latencia() -> None:
    relatorio = {
        "prompt_version": "semana4-v1",
        "status_cientifico": "COLETA_CONCLUIDA_REVISAO_PENDENTE",
        "execucao_real": True,
        "resumos": {
            "qwen2.5:7b": {"gerados": 4, "p95_wall_ms": 6100.0, "dentro_meta_rnf04_8s": True},
            "qwen2.5:14b": {"gerados": 4, "p95_wall_ms": None, "dentro_meta_rnf04_8s": False},
        },
    }
    registros = {r.run_name: r for r in registros_semana4(relatorio)}
    assert registros["semana4_qwen2.5:7b"].metrics["dentro_meta_rnf04_8s"] == 1.0
    assert "p95_wall_ms" not in registros["semana4_qwen2.5:14b"].metrics
    assert registros["semana4_qwen2.5:14b"].tags["status_cientifico"].startswith("COLETA")


def test_backfill_mlflow_quando_json_ja_existe_sem_duplicar_arquivo(tmp_path: Path) -> None:
    artefato = tmp_path / "seguranca.json"
    artefato.write_text(json.dumps(_seguranca()), encoding="utf-8")
    tracker = MLflowExperimentTracker(raiz_repo=tmp_path)

    # 1ª rodada sem MLflow ativo: grava apenas JSON local.
    assert registrar(tracker, "seguranca", artefato, "teste") == (2, 0)
    arquivos_iniciais = list(tracker.pasta_runs.glob("run_*.json"))
    assert len(arquivos_iniciais) == 2

    # 2ª rodada com MLflow ativo, mas ainda vazio: sincroniza no MLflow sem duplicar JSON.
    registrados_mlflow: list[str] = []

    class _RunCtx:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *args: object) -> None:
            return None

    def _start_run(run_name: str) -> _RunCtx:
        registrados_mlflow.append(run_name)
        return _RunCtx()

    fake_mlflow = types.SimpleNamespace(
        set_tracking_uri=lambda uri: None,
        set_experiment=lambda name: None,
        get_experiment_by_name=lambda name: None,
        start_run=_start_run,
        log_params=lambda p: None,
        log_metrics=lambda m: None,
        set_tags=lambda t: None,
    )
    with patch.dict(sys.modules, {"mlflow": fake_mlflow}):
        assert registrar(tracker, "seguranca", artefato, "teste") == (2, 0)

    assert len(list(tracker.pasta_runs.glob("run_*.json"))) == 2
    assert sorted(registrados_mlflow) == ["seguranca_B_llm_com_rag", "seguranca_C_rag_sem_llm"]


def test_semana4_avaliacao_registra_notas_e_ragas() -> None:
    relatorio = {
        "rubric_version": "semana4-eval-v1",
        "evaluator_model": "qwen2.5:14b",
        "embedding_model": "bge-m3",
        "execucao_real": True,
        "revisao_humana_realizada": False,
        "status_cientifico": "AVALIACAO_AUTOMATICA_CONCLUIDA_SEM_REVISAO_HUMANA",
        "timestamp_utc": "2026-11-19T12:35:00+00:00",
        "resumos_por_modelo": {
            "qwen2.5:7b": {
                "status_modelo": "APROVADO_COM_OMISSOES_PENDENTE_REVISAO",
                "nota_qualidade_geral_0_10": 8.95,
                "nota_deterministica_0_10": 10.0,
                "nota_juiz_llm_0_10": 8.5,
                "media_fidelidade_0_10": 9.3,
                "media_completude_0_10": 7.5,
                "afirmacoes_contraditas": 0,
                "casos_com_omissoes": 1,
                "ragas_faithfulness": 0.94,
                "ragas_answer_relevancy": 0.91,
                "p95_wall_ms": 17867.63,
            }
        },
    }
    [registro] = registros_semana4_avaliacao(relatorio)
    assert registro.run_name == "semana4_avaliacao_qwen2.5:7b"
    assert registro.metrics["nota_qualidade_geral_0_10"] == 8.95
    assert registro.metrics["ragas_faithfulness"] == 0.94
    assert registro.metrics["revisao_humana_realizada"] == 0.0
    assert registro.tags["status_modelo"] == "APROVADO_COM_OMISSOES_PENDENTE_REVISAO"


def test_backfill_reverso_preserva_mlflow_e_reconstroi_json(tmp_path: Path) -> None:
    import hashlib

    artefato = tmp_path / "seguranca.json"
    artefato.write_text(json.dumps(_seguranca()))
    sha = hashlib.sha256(artefato.read_bytes()).hexdigest()
    tracker = MLflowExperimentTracker(raiz_repo=tmp_path)
    native = {(sha, r.run_name) for r in registros_seguranca(_seguranca())}
    with (
        patch("observability.registrar_avaliacoes.ja_registrados_no_mlflow", return_value=native),
        patch.object(tracker, "_log_to_native_mlflow_if_available") as log,
    ):
        assert registrar(tracker, "seguranca", artefato, "restauracao") == (2, 0)
        assert registrar(tracker, "seguranca", artefato, "restauracao") == (0, 2)
        log.assert_not_called()
    assert len(list(tracker.pasta_runs.glob("run_*.json"))) == 2


def test_backfill_nao_atribui_corpus_atual_ao_experimento(tmp_path: Path) -> None:
    artefato = tmp_path / "seguranca.json"
    artefato.write_text(json.dumps(_seguranca()))
    tracker = MLflowExperimentTracker(raiz_repo=tmp_path)
    with patch.object(
        tracker, "carregar_linhagem_manifesto", return_value={"combined_sha256": "novo"}
    ):
        registrar(tracker, "seguranca", artefato, "historico")
    for file in tracker.pasta_runs.glob("run_*.json"):
        tags = json.loads(file.read_text())["tags"]
        assert "combined_sha256" not in tags
        assert tags["ambiente_importacao_combined_sha256"] == "novo"
        assert tags["linhagem_experimento"] == "NAO_INFORMADA_NO_ARTEFATO"
