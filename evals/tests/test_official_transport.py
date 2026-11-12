"""Integração RAGAS instalado + SDK real + HTTP simulado. NÃO mede qualidade de LLM."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import openai
import pytest
from evals.runners.avaliar_ragas_oficial import OfficialRagasCollectionsEvaluator


def test_official_metrics_two_cases_and_persistent_cache(tmp_path: Path) -> None:
    requests: list[str] = []
    invalid = False

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(request.url.path)
        if request.url.path.endswith("/embeddings"):
            inputs = body["input"]
            size = len(inputs) if isinstance(inputs, list) else 1
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "model": "fixture-embedding",
                    "data": [
                        {"object": "embedding", "index": i, "embedding": [1.0, 0.0, 0.0]}
                        for i in range(size)
                    ],
                    "usage": {"prompt_tokens": size, "total_tokens": size},
                },
            )
        prompt = json.dumps(body)
        if "AnswerRelevanceOutput" in prompt:
            answer = {"question": "Qual o documento?", "noncommittal": 0}
        elif "NLIStatementOutput" in prompt:
            answer = {
                "statements": [
                    {"statement": "É necessário CPF.", "reason": "Fixture HTTP", "verdict": 1}
                ]
            }
        elif "StatementGeneratorOutput" in prompt:
            answer = {"statements": ["É necessário CPF."]}
        elif "ContextRecallOutput" in prompt:
            answer = {
                "classifications": [
                    {"statement": "É necessário CPF.", "reason": "Fixture HTTP", "attributed": 1}
                ]
            }
        elif "ContextPrecisionOutput" in prompt:
            answer = {"reason": "Fixture HTTP", "verdict": 1}
        else:
            raise AssertionError(f"Contrato RAGAS desconhecido: {prompt[:500]}")
        if invalid:
            answer = {}
        return httpx.Response(
            200,
            json={
                "id": "fixture",
                "object": "chat.completion",
                "created": 0,
                "model": "fixture",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(answer)},
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    class Client(openai.AsyncOpenAI):
        def __init__(self, **kwargs: object) -> None:
            configured = kwargs["http_client"]
            assert isinstance(configured, httpx.AsyncClient)
            super().__init__(
                api_key="fixture",
                base_url="http://fixture/v1",
                max_retries=0,
                http_client=httpx.AsyncClient(
                    transport=httpx.MockTransport(respond), event_hooks=configured.event_hooks
                ),
            )

    with patch.object(openai, "AsyncOpenAI", Client):
        evaluator = OfficialRagasCollectionsEvaluator(
            evaluator_model="fixture", embedding_model="fixture", metric_cache=tmp_path / "metricas"
        )
        try:
            for question in ("Qual o documento?", "Quais documentos apresentar?"):
                score = evaluator.avaliar_par_positivo(
                    pergunta=question,
                    referencia="Apresente CPF.",
                    resposta_sem_rag="Leve CPF.",
                    resposta_com_rag="Apresente CPF.",
                    contextos_com_rag=["É necessário CPF."],
                )
                assert score.com_rag_faithfulness == 1
                assert score.com_rag_answer_relevancy == pytest.approx(1)
                assert score.com_rag_context_recall == 1
                assert score.com_rag_context_precision == pytest.approx(1)
            count = len(requests)
            evaluator.avaliar_par_positivo(
                pergunta="Qual o documento?",
                referencia="Apresente CPF.",
                resposta_sem_rag="Leve CPF.",
                resposta_com_rag="Apresente CPF.",
                contextos_com_rag=["É necessário CPF."],
            )
            assert len(requests) == count
            assert any(p.endswith("/embeddings") for p in requests)
            invalid = True
            with pytest.raises(Exception) as error:
                evaluator.avaliar_par_positivo(
                    pergunta="Pergunta sem cache",
                    referencia="Apresente CPF.",
                    resposta_sem_rag="Leve CPF.",
                    resposta_com_rag="Apresente CPF.",
                    contextos_com_rag=["É necessário CPF."],
                )
            assert type(error.value).__name__ == "InstructorRetryException"
            assert len(requests) > count
            records = [
                json.loads(p.read_text(encoding="utf-8"))
                for p in (tmp_path / "http").glob("*.json")
            ]
            assert len(records) == len(requests)
            assert all(r["model"] == r["request_body"]["model"] for r in records)
        finally:
            evaluator.close()
