"""Valida todos os datasets de avaliação em evals/datasets/*.jsonl.

Reprova (código de saída 1) se algum arquivo estiver vazio, tiver linha que não é
um objeto JSON, linha sem "id" ou id repetido.

Uso (a partir da raiz do repo):
    uv run --project backend python evals/runners/validar_datasets.py
"""

import json
import sys
from pathlib import Path

PASTA_DATASETS = Path(__file__).resolve().parents[1] / "datasets"


def validar_arquivo(caminho: Path) -> list[str]:
    erros: list[str] = []
    ids_vistos: set[str] = set()
    linhas_validas = 0

    with caminho.open(encoding="utf-8") as arquivo:
        for numero, linha in enumerate(arquivo, start=1):
            if not linha.strip():
                continue
            local = f"{caminho.name}:{numero}"
            try:
                exemplo = json.loads(linha)
            except json.JSONDecodeError as erro:
                erros.append(f"{local}: JSON inválido ({erro.msg})")
                continue
            if not isinstance(exemplo, dict):
                erros.append(f"{local}: a linha precisa ser um objeto JSON")
                continue
            identificador = exemplo.get("id")
            if not identificador:
                erros.append(f"{local}: falta o campo 'id'")
            elif identificador in ids_vistos:
                erros.append(f"{local}: id repetido '{identificador}'")
            else:
                ids_vistos.add(identificador)
                linhas_validas += 1

    if linhas_validas == 0 and not erros:
        erros.append(f"{caminho.name}: arquivo sem nenhum exemplo")
    return erros


def main() -> int:
    arquivos = sorted(PASTA_DATASETS.glob("*.jsonl"))
    if not arquivos:
        print(f"Nenhum dataset encontrado em {PASTA_DATASETS}")
        return 1

    todos_os_erros: list[str] = []
    for caminho in arquivos:
        erros = validar_arquivo(caminho)
        situacao = "OK" if not erros else f"{len(erros)} erro(s)"
        print(f"{caminho.name}: {situacao}")
        todos_os_erros.extend(erros)

    for erro in todos_os_erros:
        print(f"  - {erro}")
    return 1 if todos_os_erros else 0


if __name__ == "__main__":
    sys.exit(main())
