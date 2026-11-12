"""Regressões de integridade e retomada; escores aqui são fixtures, não medidas."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

import pytest
from evals.runners import evaluation_cli
from evals.runners.artifacts import atomic_json, bind_manifest, read_json
from evals.runners.avaliar_ragas_oficial import EscoresCasoRagas
from evals.runners.collection_checkpoint import CheckpointGenerator
from evals.runners.evaluation_cli import codigo_saida
from evals.runners.factual_audit import (
    consolidar_auditoria_factual,
    gerar_template_auditoria_factual,
)

from app.application.ports import GenerationResultDTO, GeneratorPort, RetrievalHitDTO
from tests.unit.test_avaliar_ragas_oficial import _coleta_real_fixture, _StubRagasEvaluator


def reviewed(coleta: dict[str, Any]) -> dict[str, Any]:
    audit = gerar_template_auditoria_factual(coleta)
    for case in audit["casos"]:
        for arm in ("sem_rag", "com_rag"):
            case[arm].update(
                revisado=True, revisor="Fixture", observacoes="Sem afirmações factuais"
            )
    return audit


def test_rejects_stale_audit_and_edited_answer() -> None:
    coleta = _coleta_real_fixture()
    audit = reviewed(coleta)
    altered = copy.deepcopy(coleta)
    altered["casos"][0]["com_rag"]["geracao"]["text"] = "Resposta nunca auditada"
    with pytest.raises(ValueError, match="hash/schema"):
        consolidar_auditoria_factual(audit, altered)
    audit["casos"][0]["com_rag"]["resposta"] = "Texto alterado"
    with pytest.raises(ValueError, match="Resposta auditada"):
        consolidar_auditoria_factual(audit, coleta)


@pytest.mark.parametrize("count", [1.5, "2", True, -1, None])
def test_counts_are_strict_integers(count: Any) -> None:
    coleta = _coleta_real_fixture()
    audit = reviewed(coleta)
    audit["casos"][0]["sem_rag"]["afirmacoes_corretas"] = count
    with pytest.raises(ValueError, match="inteiros"):
        consolidar_auditoria_factual(audit, coleta)


def test_zero_claims_and_controls_are_reviewable() -> None:
    coleta = _coleta_real_fixture()
    audit = reviewed(coleta)
    result = consolidar_auditoria_factual(audit, coleta)
    assert result["completa"]
    assert result["sem_rag"]["taxa_contradicao_por_afirmacao"] is None
    assert result["por_origem"]["controles"]["sem_rag"]["total_casos_avaliados"] == 1
    audit["casos"][1]["sem_rag"]["revisado"] = False
    assert not consolidar_auditoria_factual(audit, coleta)["completa"]


def test_duplicates_and_missing_evidence_cannot_complete() -> None:
    coleta = _coleta_real_fixture()
    audit = reviewed(coleta)
    audit["casos"][0]["sem_rag"]["afirmacoes_corretas"] = 1
    assert not consolidar_auditoria_factual(audit, coleta)["completa"]
    audit["casos"].append(audit["casos"][0])
    with pytest.raises(ValueError, match="IDs"):
        consolidar_auditoria_factual(audit, coleta)


@pytest.mark.parametrize(
    ("complete", "review", "approved", "expected"),
    [
        (False, False, False, 1),
        (True, False, True, 3),
        (True, True, True, 0),
        (True, True, False, 2),
    ],
)
def test_exit_codes(complete: bool, review: bool, approved: bool, expected: int) -> None:
    assert (
        codigo_saida(
            {
                "avaliacao_ragas_completa": complete,
                "auditoria_factual": {"completa": review},
                "sucesso_criterios_rag": approved,
            }
        )
        == expected
    )


def test_generation_resumes_each_arm_and_binds_configuration(tmp_path: Path) -> None:
    class InterruptedGenerator(GeneratorPort):
        calls = 0
        interrupt = True

        def generate(
            self,
            question: str,
            evidences: tuple[RetrievalHitDTO, ...] = (),
            *,
            rag_mode: bool | None = None,
        ) -> GenerationResultDTO:
            self.calls += 1
            if rag_mode and self.interrupt:
                raise KeyboardInterrupt
            return GenerationResultDTO("fixture", "test", "test", bool(rag_mode))

    generator = InterruptedGenerator()
    bind_manifest(tmp_path, {"model": "fixture"})
    cache = CheckpointGenerator(generator, tmp_path / "calls")
    cache.generate("question", rag_mode=False)
    with pytest.raises(KeyboardInterrupt):
        cache.generate("question", rag_mode=True)
    generator.interrupt = False
    resumed = CheckpointGenerator(generator, tmp_path / "calls")
    resumed.generate("question", rag_mode=False)
    resumed.generate("question", rag_mode=True)
    assert generator.calls == 3
    with pytest.raises(ValueError, match="incompatível"):
        bind_manifest(tmp_path, {"model": "changed"})


def test_consolidation_never_calls_provider_and_preserves_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Evaluator(_StubRagasEvaluator):
        def close(self) -> None:
            pass

    coleta = _coleta_real_fixture()
    atomic_json(tmp_path / "resultado.json", coleta)
    monkeypatch.setattr(evaluation_cli, "ollama_identity", lambda *a: {"fixture": True})
    monkeypatch.setattr(
        evaluation_cli,
        "OfficialRagasCollectionsEvaluator",
        lambda **kw: Evaluator(EscoresCasoRagas(0.95, 0.95, 0.95, 0.95, 0.95)),
    )
    monkeypatch.setattr(sys, "argv", ["runner", "--coleta-dir", str(tmp_path)])
    assert evaluation_cli.main() == 3
    first = read_json(tmp_path / "avaliacao_ragas.json")
    atomic_json(tmp_path / "auditoria_factual_humana.json", reviewed(coleta))

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("Consolidação chamou o provedor")

    monkeypatch.setattr(evaluation_cli, "ollama_identity", forbidden)
    monkeypatch.setattr(evaluation_cli, "OfficialRagasCollectionsEvaluator", forbidden)
    monkeypatch.setattr(
        sys, "argv", ["runner", "--coleta-dir", str(tmp_path), "--consolidate-only"]
    )
    assert evaluation_cli.main() == 0
    final = read_json(tmp_path / "avaliacao_ragas.json")
    assert first["ragas_oficial"] == final["ragas_oficial"]
    assert len(list((tmp_path / "ragas_v1/consolidacoes").glob("*/avaliacao_ragas.json"))) == 2
    assert read_json(tmp_path / "resultado.json") == coleta


def test_judge_retry_is_explicit_bounded_and_keeps_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Evaluator(_StubRagasEvaluator):
        def close(self) -> None:
            pass

    atomic_json(tmp_path / "resultado.json", _coleta_real_fixture())
    calls = []

    def factory(**kwargs: Any) -> Evaluator:
        calls.append(1)
        return Evaluator(RuntimeError("fixture timeout"))

    monkeypatch.setattr(evaluation_cli, "ollama_identity", lambda *a: {"fixture": True})
    monkeypatch.setattr(evaluation_cli, "OfficialRagasCollectionsEvaluator", factory)
    monkeypatch.setattr(sys, "argv", ["runner", "--coleta-dir", str(tmp_path)])
    assert evaluation_cli.main() == 1
    assert evaluation_cli.main() == 1
    assert len(calls) == 1
    monkeypatch.setattr(sys, "argv", ["runner", "--coleta-dir", str(tmp_path), "--retry-failed"])
    for _ in range(3):
        assert evaluation_cli.main() == 1
    assert len(calls) == 3
    record = read_json(next((tmp_path / "ragas_v1/pares").glob("*.json")))
    assert len(record["attempts"]) == 3
