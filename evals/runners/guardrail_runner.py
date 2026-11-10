"""Avalia um guardrail clínico contra o dataset rotulado.

Uso (a partir da raiz do repo):
    uv run --project backend python evals/runners/guardrail_runner.py \
        --alvo evals.baselines.palavras_chave:deve_bloquear

O alvo é qualquer função `(pergunta: str) -> bool` que devolve True para bloquear.
"""

import argparse
import importlib
import json
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
# Permite importar tanto `evals.*` quanto `app.*` (pacote do backend).
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "backend"))

DATASET_PADRAO = RAIZ / "evals" / "datasets" / "guardrail_clinico_v1.jsonl"
PASTA_RELATORIOS = RAIZ / "evals" / "reports"


@dataclass
class Resultado:
    total: int = 0
    deviam_bloquear: int = 0
    bloqueados_corretamente: int = 0
    deviam_permitir: int = 0
    bloqueados_indevidamente: int = 0
    erros: list[dict[str, str]] = field(default_factory=list)

    @property
    def recall_bloqueio(self) -> float:
        """De tudo que devia ser bloqueado, quanto foi bloqueado. A métrica de segurança."""
        if not self.deviam_bloquear:
            return 0.0
        return self.bloqueados_corretamente / self.deviam_bloquear

    @property
    def taxa_falso_bloqueio(self) -> float:
        """De tudo que devia passar, quanto foi bloqueado à toa. A métrica de utilidade."""
        if not self.deviam_permitir:
            return 0.0
        return self.bloqueados_indevidamente / self.deviam_permitir


def carregar_dataset(caminho: Path) -> list[dict[str, str]]:
    with caminho.open(encoding="utf-8") as arquivo:
        return [json.loads(linha) for linha in arquivo if linha.strip()]


def carregar_alvo(referencia: str) -> Callable[[str], bool]:
    modulo, _, funcao = referencia.partition(":")
    alvo: Callable[[str], bool] = getattr(importlib.import_module(modulo), funcao)
    return alvo


def avaliar(exemplos: list[dict[str, str]], alvo: Callable[[str], bool]) -> Resultado:
    resultado = Resultado(total=len(exemplos))
    for exemplo in exemplos:
        bloqueou = alvo(exemplo["pergunta"])
        if exemplo["esperado"] == "bloquear":
            resultado.deviam_bloquear += 1
            if bloqueou:
                resultado.bloqueados_corretamente += 1
            else:
                resultado.erros.append({**exemplo, "erro": "deixou passar"})
        else:
            resultado.deviam_permitir += 1
            if bloqueou:
                resultado.bloqueados_indevidamente += 1
                resultado.erros.append({**exemplo, "erro": "bloqueou à toa"})
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alvo", required=True, help="modulo:funcao a avaliar")
    parser.add_argument("--dataset", type=Path, default=DATASET_PADRAO)
    parser.add_argument("--min-recall", type=float, default=0.0)
    parser.add_argument("--max-falso-bloqueio", type=float, default=1.0)
    args = parser.parse_args()

    resultado = avaliar(carregar_dataset(args.dataset), carregar_alvo(args.alvo))

    print(f"Alvo: {args.alvo}")
    print(f"Recall de bloqueio:   {resultado.recall_bloqueio:.2%}")
    print(f"Taxa falso bloqueio:  {resultado.taxa_falso_bloqueio:.2%}")
    for erro in resultado.erros:
        print(f"  [{erro['id']}] {erro['erro']}: {erro['pergunta']}")

    PASTA_RELATORIOS.mkdir(exist_ok=True)
    relatorio = {
        "alvo": args.alvo,
        "dataset": args.dataset.name,
        "executado_em": datetime.now(UTC).isoformat(),
        "recall_bloqueio": resultado.recall_bloqueio,
        "taxa_falso_bloqueio": resultado.taxa_falso_bloqueio,
        **asdict(resultado),
    }
    destino = PASTA_RELATORIOS / "guardrail_ultimo.json"
    destino.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Relatório salvo em {destino.relative_to(RAIZ)}")

    reprovou = (
        resultado.recall_bloqueio < args.min_recall
        or resultado.taxa_falso_bloqueio > args.max_falso_bloqueio
    )
    if reprovou:
        print("REPROVADO: abaixo das metas definidas.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
