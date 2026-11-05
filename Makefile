.PHONY: help install dev-install lint format test run-api run-ui eval eval-guardrail docker-build docker-up clean

help:
	@echo "Comandos disponíveis no SUS Cidadão:"
	@echo "  make dev-install    - Instala dependências no backend com uv"
	@echo "  make lint           - Executa Ruff e Mypy no backend"
	@echo "  make format         - Formata o código com Ruff"
	@echo "  make test           - Executa os testes no backend"
	@echo "  make run-api        - Inicia a API FastAPI (0.0.0.0:8000)"
	@echo "  make run-ui         - Orientações da interface mobile (React Native)"
	@echo "  make eval           - Valida os datasets e avalia o guardrail (baseline)"
	@echo "  make eval-guardrail - Executa a avaliação do guardrail clínico"
	@echo "  make docker-build   - Constrói a imagem Docker do backend"
	@echo "  make clean          - Limpa caches e artefatos temporários"

dev-install:
	cd backend && uv sync

lint:
	cd backend && uv run ruff check .
	cd backend && uv run mypy app tests

format:
	cd backend && uv run ruff format .

test:
	cd backend && uv run pytest

run-api:
	cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-ui:
	@echo "Interface do Cidadão em React Native (mobile/). Consulte docs/adr/0002_mobile_first_react_native_client.md"

eval:
	uv run --project backend python evals/runners/validar_datasets.py
	uv run --project backend python evals/runners/guardrail_runner.py --alvo evals.baselines.palavras_chave:deve_bloquear

eval-guardrail:
	uv run --project backend python evals/runners/guardrail_runner.py --alvo evals.baselines.palavras_chave:deve_bloquear

docker-build:
	docker build -t sus-cidadao-backend:latest backend

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
