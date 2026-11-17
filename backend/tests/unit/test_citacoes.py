"""Item 4: citação por ID (semana3-v3) e citações fora do texto julgado (ragas_v2)."""

from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import patch

import pytest
from evals.runners.avaliar_ragas_oficial import EscoresCasoRagas, avaliar_coleta_ragas

from app.application.ports import RetrievalHitDTO
from app.infrastructure.llm.generator import (
    PROMPT_VERSION,
    PROMPT_VERSION_V3,
    SYSTEM_PROMPT_V3,
    OllamaRESTGeneratorAdapter,
    build_generator,
    montar_prompt,
)
from app.seguranca.citacoes import expandir_citacoes, ids_citados, remover_citacoes
from app.seguranca.saida import validar_saida


def _hit(chunk_id: str, titulo: str = "Portaria GM/MS nº 3.677/2024", pagina: int = 11) -> Any:
    return RetrievalHitDTO(chunk_id, 1.0, "src", titulo, "s", pagina, "FARMACIA_POPULAR", "texto")


def test_id_recuperado_vira_citacao_completa_com_titulo_e_pagina() -> None:
    texto, contagem = expandir_citacoes(
        "Leve CPF e receita [CHK-PFPB-001].", [_hit("CHK-PFPB-001")]
    )
    assert (
        texto == "Leve CPF e receita [Fonte: CHK-PFPB-001 | Portaria GM/MS nº 3.677/2024, p. 11]."
    )
    assert contagem == {"validas": 1, "fora_do_contexto": 0}


def test_id_inventado_continua_visivel_e_a_saida_barra() -> None:
    texto, contagem = expandir_citacoes("Vale grátis [CHK-FALSO-9].", [_hit("CHK-PFPB-001")])
    assert "[Fonte: CHK-FALSO-9 | FORA_DO_CONTEXTO]" in texto
    assert contagem == {"validas": 0, "fora_do_contexto": 1}
    assert "CITACAO_FORA_DO_CONTEXTO" in validar_saida(texto, ["CHK-PFPB-001"]).motivos


def test_dois_ids_no_mesmo_colchete() -> None:
    hits = [_hit("CHK-A", "Título A", 1), _hit("CHK-B", "Título B", 2)]
    texto, contagem = expandir_citacoes("Retire na UBS [CHK-A, CHK-B].", hits)
    assert "[Fonte: CHK-A | Título A, p. 1] [Fonte: CHK-B | Título B, p. 2]" in texto
    assert contagem["validas"] == 2
    assert ids_citados("[CHK-A; CHK-B] e [CHK-C]") == ["CHK-A", "CHK-B", "CHK-C"]


def test_id_curto_sem_expandir_tambem_e_barrado_na_saida() -> None:
    # Achado do item 2: "[CHK-FALSO]" sem "Fonte:" passava pela validação de saída.
    resultado = validar_saida("Pode retirar de graça [CHK-PORTARIA-FALSA-999].", ["CHK-A"])
    assert resultado.motivos == ("CITACAO_FORA_DO_CONTEXTO",)
    assert validar_saida("Pode retirar de graça [CHK-A].", ["CHK-A"]).aprovada


def test_remover_citacoes_deixa_so_o_texto() -> None:
    texto = (
        "A losartana é gratuita [Fonte: CHK-A | Portaria, p. 1]. Leve CPF [CHK-B]. "
        "[Fonte: Conhecimento Geral]"
    )
    assert remover_citacoes(texto) == "A losartana é gratuita. Leve CPF."


def test_prompt_v3_mostra_so_o_id_para_citar() -> None:
    prompt = montar_prompt("onde pego?", (_hit("CHK-PFPB-001"),), PROMPT_VERSION_V3)
    assert "ID para citar: [CHK-PFPB-001]" in prompt
    assert "Portaria GM/MS" not in prompt
    padrao = montar_prompt("onde pego?", (_hit("CHK-PFPB-001"),))
    # A esteira normaliza NFKC: "nº" vira "no" no prompt. No v2 o modelo copiava isso;
    # no v3 o título vem dos metadados, sem passar pela normalização.
    assert "[Fonte: CHK-PFPB-001 | Portaria GM/MS no 3.677/2024, p. 11]" in padrao


def test_versao_padrao_continua_v2_e_versao_invalida_falha() -> None:
    assert build_generator("ollama", model_name="m").prompt_version == PROMPT_VERSION  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="Versão de prompt"):
        build_generator("ollama", model_name="m", prompt_version="semana3-v9")


def _resposta_ollama(texto: str) -> io.BytesIO:
    corpo = {"model": "m", "done": True, "done_reason": "stop", "response": texto}
    resposta = io.BytesIO(json.dumps(corpo).encode())
    resposta.__enter__ = lambda: resposta  # type: ignore[method-assign]
    resposta.__exit__ = lambda *a: None  # type: ignore[method-assign]
    return resposta


def test_gerador_v3_expande_e_guarda_so_a_contagem() -> None:
    gerador = OllamaRESTGeneratorAdapter(
        base_url="http://localhost:11434", model_name="m", prompt_version=PROMPT_VERSION_V3
    )
    pedidos: list[dict[str, Any]] = []

    def urlopen(request: Any, timeout: float) -> io.BytesIO:
        pedidos.append(json.loads(request.data))
        return _resposta_ollama("Retire na Farmácia Popular [CHK-PFPB-001].")

    with patch("urllib.request.urlopen", urlopen):
        resultado = gerador.generate(
            "onde pego losartana de graça?", (_hit("CHK-PFPB-001"),), rag_mode=True
        )
    assert pedidos[0]["system"] == SYSTEM_PROMPT_V3
    assert resultado.text.endswith("[Fonte: CHK-PFPB-001 | Portaria GM/MS nº 3.677/2024, p. 11].")
    metadados = resultado.provider_metadata or {}
    assert metadados["citacoes_por_id"] == {"validas": 1, "fora_do_contexto": 0}
    assert "Farmácia" not in json.dumps(metadados, ensure_ascii=False)


class _AvaliadorQueGuardaRespostas:
    evaluator_provider = "stub"
    evaluator_model = "m"
    embedding_model = "e"

    def __init__(self) -> None:
        self.respostas: list[str] = []

    def avaliar_par_positivo(self, **kwargs: Any) -> EscoresCasoRagas:
        self.respostas += [kwargs["resposta_sem_rag"], kwargs["resposta_com_rag"]]
        return EscoresCasoRagas(0.5, 0.9, 0.9, 0.9, 0.9)


def _coleta() -> dict[str, Any]:
    braco = {
        "pergunta": "Como retirar losartana?",
        "referencia": "Na Farmácia Popular com CPF.",
        "evidencias": [{"chunk_id": "CHK-A", "text": "Farmácia Popular exige CPF."}],
    }
    return {
        "tipo_execucao": "COLETA_REAL",
        "total_casos": 1,
        "pares_invalidos": 0,
        "execucao_completa": True,
        "protocolo": {},
        "sha256": {},
        "casos": [
            {
                "caso_id": "GOLD-001",
                "status_par": "PAR_LLM",
                "categoria": "POSITIVO",
                "sem_rag": {**braco, "geracao": {"text": "Vá à farmácia."}},
                "com_rag": {
                    **braco,
                    "geracao": {"text": "Leve CPF [Fonte: CHK-A | Portaria, p. 1]."},
                },
            }
        ],
    }


def test_juiz_ptbr_recebe_resposta_sem_citacao_e_original_fica_intacto() -> None:
    coleta = _coleta()
    avaliador = _AvaliadorQueGuardaRespostas()
    relatorio = avaliar_coleta_ragas(coleta, avaliador=avaliador, protocolo_juiz="ptbr_sem_citacao")
    assert avaliador.respostas == ["Vá à farmácia.", "Leve CPF."]
    assert relatorio["ragas_oficial"]["protocolo_juiz"] == "ptbr_sem_citacao"
    assert coleta["casos"][0]["com_rag"]["geracao"]["text"].endswith("p. 1].")

    original = _AvaliadorQueGuardaRespostas()
    avaliar_coleta_ragas(_coleta(), avaliador=original)
    assert original.respostas[1] == "Leve CPF [Fonte: CHK-A | Portaria, p. 1]."


def test_protocolo_de_juiz_desconhecido_falha() -> None:
    with pytest.raises(ValueError, match="Protocolo de juiz"):
        avaliar_coleta_ragas(
            _coleta(), avaliador=_AvaliadorQueGuardaRespostas(), protocolo_juiz="x"
        )
