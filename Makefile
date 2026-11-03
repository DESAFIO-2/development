.PHONY: help install dev-install lint format test test-unit test-integration run-api run-ui eval clean docker-build docker-up

help:
	@echo "Comandos disponíveis no SUS Cidadão:"
	@echo "  make install        - Instala dependências de produção"
	@echo "  make dev-install    - Instala dependências de desenvolvimento, evals e UI"
	@echo "  make lint           - Executa Ruff e Mypy"
	@echo "  make format         - Formata código com Ruff"
	@echo "  make test           - Executa todos os testes"
	@echo "  make test-unit      - Executa apenas testes unitários"
	@echo "  make run-api        - Inicia a API FastAPI (0.0.0.0:8000)"
	@echo "  make run-ui         - Inicia a interface Streamlit"
	@echo "  make eval           - Executa benchmark com RAGAS"
	@echo "  make docker-build   - Constrói a imagem Docker da aplicação"
	@echo "  make docker-up      - Sobe os serviços via Docker Compose"
	@echo "  make clean          - Limpa caches e artefatos temporários"

install:
	pip install -e .

dev-install:
	pip install -e ".[dev,eval,observability,ui,multimodal]"

lint:
	ruff check src tests evals
	mypy src/challenge2

format:
	ruff format src tests evals

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

run-api:
	uvicorn challenge2.api.main:app --host 0.0.0.0 --port 8000 --reload

run-ui:
	streamlit run src/challenge2/ui/app_streamlit.py --server.port 8501

eval:
	python evals/runners/ragas_runner.py

docker-build:
	docker build -t challenge2-api:latest -f deploy/docker/Dockerfile .

docker-up:
	docker compose -f deploy/docker/compose.yaml up -d

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
