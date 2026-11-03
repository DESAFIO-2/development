import json
from pathlib import Path

DATASET = Path(__file__).resolve().parents[3] / "evals" / "datasets" / "guardrail_clinico_v1.jsonl"
CAMPOS = {"id", "pergunta", "esperado", "categoria"}


def _exemplos() -> list[dict[str, str]]:
    with DATASET.open(encoding="utf-8") as arquivo:
        return [json.loads(linha) for linha in arquivo if linha.strip()]


def test_todo_exemplo_tem_os_campos_obrigatorios() -> None:
    for exemplo in _exemplos():
        assert set(exemplo) == CAMPOS, exemplo


def test_rotulos_validos() -> None:
    for exemplo in _exemplos():
        assert exemplo["esperado"] in {"bloquear", "permitir"}, exemplo


def test_ids_nao_se_repetem() -> None:
    ids = [exemplo["id"] for exemplo in _exemplos()]
    assert len(ids) == len(set(ids))


def test_dataset_tem_as_duas_classes() -> None:
    rotulos = {exemplo["esperado"] for exemplo in _exemplos()}
    assert rotulos == {"bloquear", "permitir"}
