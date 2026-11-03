.PHONY: help install dev-install lint format test run-api run-ui eval docker-build docker-up clean

help:
	@echo "Comandos disponíveis no SUS Cidadão:"
	@echo "  make dev-install    - Instala dependências no backend com uv"
	@echo "  make lint           - Executa Ruff e Mypy no backend"
	@echo "  make format         - Formata o código com Ruff"
	@echo "  make test           - Executa os testes no backend"
	@echo "  make run-api        - Inicia a API FastAPI (0.0.0.0:8000)"
	@echo "  make run-ui         - Inicia a interface Streamlit"
	@echo "  make eval           - Executa o benchmark com RAGAS"
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
	streamlit run frontend/app_streamlit.py --server.port 8501

eval:
	python evals/runners/ragas_runner.py

docker-build:
	docker build -t sus-cidadao-backend:latest backend

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
