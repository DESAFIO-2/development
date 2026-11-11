"""Revisão humana vinculada à coleta completa, incluindo controles separados."""

from __future__ import annotations

from typing import Any

from evals.runners.artifacts import digest

CONTAGENS = ("afirmacoes_corretas", "afirmacoes_contraditas", "afirmacoes_nao_verificaveis")


def gerar_template_auditoria_factual(coleta: dict[str, Any]) -> dict[str, Any]:
    casos = []
    for caso in coleta["casos"]:
        item: dict[str, Any] = {
            "caso_id": caso["caso_id"],
            "categoria": caso["categoria"],
            "status_par": caso["status_par"],
            "caso_sha256": digest(caso),
            "pergunta": caso["com_rag"]["pergunta"],
            "referencia_normativa": caso["com_rag"]["referencia"],
        }
        for braco in ("sem_rag", "com_rag"):
            geracao = caso[braco]["geracao"]
            item[braco] = {
                "resposta": geracao["text"],
                "resposta_sha256": digest(geracao["text"]),
                "origem": geracao.get(
                    "execution_kind", "llm" if caso["status_par"] == "PAR_LLM" else "controle"
                ),
                **dict.fromkeys(CONTAGENS, 0),
                "revisor": "",
                "revisado": False,
                "observacoes": "",
                "evidencias": [],
            }
        casos.append(item)
    return {
        "schema_version": "auditoria-factual-v2",
        "coleta_sha256": digest(coleta),
        "instrucoes": (
            "Revisar TODAS as respostas contra fontes normativas independentes, por medicamento. "
            "O gabarito orienta a revisão, mas não é prova suficiente. Registrar revisor, "
            "observacoes e evidencias (documento, página/seção e fato verificado); contar "
            "afirmações corretas, contraditas e não verificáveis separadamente. "
            "Se não houver afirmações factuais, deixar zero e justificar em observacoes. "
            "Não alterar campos de identidade, resposta ou referência. Só marcar revisado "
            "após concluir. Esta ficha identifica os braços: revisão não cega."
        ),
        "casos": casos,
    }


def consolidar_auditoria_factual(
    auditoria: dict[str, Any], coleta: dict[str, Any]
) -> dict[str, Any]:
    esperado = gerar_template_auditoria_factual(coleta)
    pendente = {"completa": False, "sem_rag": None, "com_rag": None}
    if (
        auditoria.get("schema_version") != esperado["schema_version"]
        or auditoria.get("coleta_sha256") != esperado["coleta_sha256"]
    ):
        raise ValueError("Auditoria incompatível com a coleta: hash/schema divergente")
    itens = auditoria.get("casos", [])
    mapa = {c["caso_id"]: c for c in itens}
    if len(mapa) != len(itens) or set(mapa) != {c["caso_id"] for c in esperado["casos"]}:
        raise ValueError("Auditoria contém IDs duplicados, ausentes ou inesperados")
    grupos: dict[str, dict[str, list[dict[str, Any]]]] = {
        grupo: {b: [] for b in ("sem_rag", "com_rag")} for grupo in ("todas", "llm", "controles")
    }
    incompleta = False
    for original in esperado["casos"]:
        item = mapa[original["caso_id"]]
        for chave in ("caso_sha256", "pergunta", "referencia_normativa", "categoria", "status_par"):
            if item.get(chave) != original[chave]:
                raise ValueError(f"Identidade da auditoria alterada: {original['caso_id']}")
        for braco in ("sem_rag", "com_rag"):
            bloco = item[braco]
            for chave in ("resposta", "resposta_sha256", "origem"):
                if bloco.get(chave) != original[braco][chave]:
                    raise ValueError(f"Resposta auditada divergente: {original['caso_id']}/{braco}")
            for chave in CONTAGENS:
                valor = bloco.get(chave)
                if type(valor) is not int or valor < 0:
                    raise ValueError("Contagens factuais devem ser inteiros não negativos")
            if bloco.get("revisado") is not True:
                incompleta = True
                continue
            if (
                not str(bloco.get("revisor", "")).strip()
                or not str(bloco.get("observacoes", "")).strip()
            ):
                incompleta = True
            if sum(bloco[c] for c in CONTAGENS) and not (
                isinstance(bloco.get("evidencias"), list)
                and bloco["evidencias"]
                and all(isinstance(e, str) and e.strip() for e in bloco["evidencias"])
            ):
                incompleta = True
            grupos["todas"][braco].append(bloco)
            grupos["llm" if bloco["origem"] == "llm" else "controles"][braco].append(bloco)
    if incompleta:
        return pendente

    def resumir(blocos: list[dict[str, Any]]) -> dict[str, Any]:
        contagens = {c: sum(b[c] for b in blocos) for c in CONTAGENS}
        total = sum(contagens.values())
        contraditas = contagens["afirmacoes_contraditas"]
        nv = contagens["afirmacoes_nao_verificaveis"]
        return {
            **contagens,
            "total_casos_avaliados": len(blocos),
            "total_afirmacoes": total,
            "taxa_contradicao_por_afirmacao": contraditas / total if total else None,
            "taxa_nao_verificavel_por_afirmacao": nv / total if total else None,
            "taxa_afirmacoes_nao_confirmadas": (contraditas + nv) / total if total else None,
            "taxa_casos_com_contradicao": sum(b["afirmacoes_contraditas"] > 0 for b in blocos)
            / len(blocos)
            if blocos
            else None,
        }

    return {
        "completa": True,
        "coleta_sha256": esperado["coleta_sha256"],
        "auditoria_sha256": digest(auditoria),
        **{b: resumir(grupos["todas"][b]) for b in ("sem_rag", "com_rag")},
        "por_origem": {
            g: {b: resumir(v) for b, v in braços.items()}
            for g, braços in grupos.items()
            if g != "todas"
        },
    }
