DATASET ?= evals/datasets/golden_set_v1.jsonl
MODEL ?= qwen2.5:14b
EMBED_MODEL ?= bge-m3
COLETA_DIR ?=
LOCAL_MODEL ?= semana3-qwen14
RUN_DIR ?= evals/reports/quinta_coleta
PILOT_DIR ?= evals/reports/quinta_piloto

.PHONY: help install dev-install eval-setup lint format test run-api run-ui eval eval-guardrail demo benchmark compare compare-ollama eval-ragas compare-smoke docker-build clean

help:
	@echo "Comandos disponíveis no SUS Cidadão:"
	@echo "  make dev-install    - Instala dependências no backend com uv"
	@echo "  make eval-setup     - Instala ambiente isolado de avaliação (ragas==0.4.3) em evals/"
	@echo "  make lint           - Executa Ruff e Mypy no backend"
	@echo "  make format         - Formata o código com Ruff"
	@echo "  make test           - Executa os testes no backend"
	@echo "  make run-api        - Inicia a API FastAPI (0.0.0.0:8000)"
	@echo "  make run-ui         - Orientações da interface mobile (React Native)"
	@echo "  make eval           - Valida os datasets e avalia os guardrails"
	@echo "  make eval-guardrail - Executa a avaliação do guardrail clínico em produção"
	@echo "  make demo           - Executa a demonstração do RAG para as Personas Dona Helena e Lucas"
	@echo "  make benchmark      - Executa o benchmark determinístico (dataset configurável com DATASET)"
	@echo "  make compare        - Coleta respostas reais (configurar modelo; RAGAS pendente)"
	@echo "  make compare-ollama - Estágio 1: Coleta pareada via Ollama local (MODEL=qwen2.5:14b)"
	@echo "  make eval-ragas     - Estágio 2: Avalia coleta real com RAGAS oficial (COLETA_DIR=...)"
	@echo "  make compare-smoke  - Testa o protocolo com fixture sintética offline"
	@echo "  make docker-build   - Constrói a imagem Docker do backend"
	@echo "  make clean          - Limpa caches e artefatos temporários"

dev-install:
	cd backend && uv sync --locked

eval-setup:
	cd evals && uv sync --locked

lint:
	cd backend && uv run ruff check . ../evals ../observability
	cd backend && uv run mypy app tests ../evals/runners ../evals/baselines ../observability

format:
	cd backend && uv run ruff format . ../evals ../observability

test:
	cd backend && uv run pytest

run-api:
	cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-ui:
	@echo "Interface React Native planejada. Consulte docs/adr/0002_mobile_first_react_native_client.md"

eval:
	uv run --project backend python evals/runners/validar_datasets.py
	uv run --project backend python evals/runners/guardrail_runner.py --alvo app.guardrails.clinical:deve_bloquear

eval-guardrail:
	uv run --project backend python evals/runners/guardrail_runner.py --alvo app.guardrails.clinical:deve_bloquear

demo:
	uv run --project backend python evals/runners/demo_rag_runner.py --caso helena
	uv run --project backend python evals/runners/demo_rag_runner.py --caso lucas

benchmark:
	uv run --project backend python evals/runners/ragas_runner.py --dataset "$(DATASET)"

compare-smoke:
	uv run --project backend python evals/runners/comparar_semana3.py --synthetic-smoke --dataset "$(DATASET)"

compare:
	uv run --project backend python evals/runners/comparar_semana3.py --dataset "$(DATASET)"

compare-ollama:
	uv run --project backend python evals/runners/comparar_semana3.py --provider ollama --model "$(MODEL)" --dataset "$(DATASET)"

eval-ragas:
	uv run --project evals python evals/runners/avaliar_ragas_oficial.py --coleta-dir "$(COLETA_DIR)" --evaluator-model "$(MODEL)" --embedding-model "$(EMBED_MODEL)"

.PHONY: semana3-pilot semana3-run semana3-finalize eval-test

eval-test:
	uv run --project evals pytest evals/tests -q

semana3-pilot:
	uv run --project backend python evals/runners/semana3_local.py --pilot --run-dir "$(PILOT_DIR)" --model "$(LOCAL_MODEL)" --embedding-model "$(EMBED_MODEL)" --dataset evals/datasets/golden_set_v2_consolidado.jsonl

semana3-run:
	uv run --project backend python evals/runners/semana3_local.py --run-dir "$(RUN_DIR)" --model "$(LOCAL_MODEL)" --embedding-model "$(EMBED_MODEL)" --dataset evals/datasets/golden_set_v2_consolidado.jsonl

semana3-finalize:
	uv run --project evals python evals/runners/avaliar_ragas_oficial.py --coleta-dir "$(RUN_DIR)" --consolidate-only

docker-build:
	docker build -t sus-cidadao-backend:latest -f backend/Dockerfile .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
