DATASET ?= evals/datasets/golden_set_v2_consolidado.jsonl
MODEL ?= qwen2.5:14b
EMBED_MODEL ?= bge-m3
COLETA_DIR ?=
LOCAL_MODEL ?= semana3-qwen14
RUN_DIR ?= evals/reports/quinta_coleta
PILOT_DIR ?= evals/reports/quinta_piloto
RUN_DIR_BLINDADO ?= evals/reports/coleta_blindada
SEG_DIR ?= evals/reports/seguranca_variantes
COLETA_PADRAO ?= $(RUN_DIR)
QUATRO_DIR ?= evals/reports/quatro_bracos
MLFLOW_VERSAO ?= 3.18.0
ROTULO ?=
RUN_DIR_V3 ?= evals/reports/coleta_v3
RUN_DIR_BLINDADO_V3 ?= evals/reports/coleta_blindada_v3
SEG_DIR_V2 ?= evals/reports/seguranca_variantes_v2
REGRA_CLINICA ?= v1_bloqueio
QUATRO_DIR_V3 ?= evals/reports/quatro_bracos_v3
HOLDOUT ?= evals/datasets/holdout_guardrail_v1.jsonl

.PHONY: help dev-install eval-setup lint format test run-api run-ui eval eval-guardrail demo benchmark compare compare-ollama eval-ragas compare-smoke docker-build clean

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
	@echo "  make semana3-run-blindado  - Braço D: coleta + RAGAS com esteira de entrada e validação de saída"
	@echo "  make seguranca-smoke       - Suíte de segurança dos 4 braços com fixture sintética (não mede LLM)"
	@echo "  make seguranca-run         - Suíte de segurança dos 4 braços com o modelo local (LOCAL_MODEL)"
	@echo "  make dast                  - ZAP + Schemathesis contra a API em container (gratuito, sem LLM)"
	@echo "  make strix-local           - Pentest Strix contra o backend (STRIX_LLM=..., ver docs/security)"
	@echo "  make semana3-quatro-bracos - Tabela única dos 4 braços e braço escolhido (COLETA_PADRAO=...)"
	@echo "  make ragas-v2-reavaliar    - Reavalia uma coleta com juiz pt-BR sem citações (COLETA_DIR=...)"
	@echo "  make semana3-run-v3        - Coleta nova com citação por ID (semana3-v3) + juiz ragas_v2"
	@echo "  make semana3-run-blindado-v3 - Braço D com prompt semana3-v3 + juiz ragas_v2"
	@echo "  make seguranca-run-v2      - Suíte v2 (injeção indireta) com o modelo local (REGRA_CLINICA=...)"
	@echo "  make semana3-quatro-bracos-v3 - Tabela dos 4 braços da rodada v3"
	@echo "  make guardrail-holdout     - Camada 1, camada 2 (Llama Guard 3) e as duas no holdout"
	@echo "  make demo-agents           - Executa os 5 cenários da orquestração Semana 4 via API"
	@echo "  make semana4-pilot         - Piloto MacBook/Ollama (2 cenários, Qwen2.5 7B vs 14B)"
	@echo "  make semana4-compare       - Comparativo completo Semana 4 no Ollama local"
	@echo "  make semana4-eval          - Avaliação automatizada Semana 4 (controles + Juiz LLM + RAGAS)"
	@echo "  make demo-multimodal       - Demonstração multimodal Semana 5 (PDF digital + texto/áudio)"
	@echo "  make eval-multimodal       - Avaliação multimodal Semana 5 (--synthetic-smoke ou faster-whisper)"
	@echo "  make registrar-avaliacoes  - Registra no MLflow os resultados de uma rodada (ROTULO=..., ARTEFATOS=...)"
	@echo "  make mlflow-ui             - Abre o MLflow local em http://127.0.0.1:5050"
	@echo "  make docker-build  - Constrói a imagem Docker do backend"
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
	cd backend && uv run python -c "import os, pathlib, uvicorn; p = pathlib.Path('.env'); [os.environ.setdefault(k.strip(), v.strip()) for line in (p.read_text(encoding='utf-8').splitlines() if p.exists() else []) if line.strip() and not line.lstrip().startswith('#') and '=' in line for k, v in [line.split('=', 1)]]; uvicorn.run('app.main:app', host='0.0.0.0', port=8000, reload=True)"

run-ui:
	cd mobile && npx expo start

eval:
	uv run --project backend python evals/runners/validar_datasets.py
	uv run --project backend python evals/runners/guardrail_runner.py --alvo app.guardrails.clinical:deve_bloquear --min-recall 1.0 --max-falso-bloqueio 0.05

eval-guardrail:
	uv run --project backend python evals/runners/guardrail_runner.py --alvo app.guardrails.clinical:deve_bloquear --min-recall 1.0 --max-falso-bloqueio 0.05

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

.PHONY: semana3-run-blindado seguranca-smoke seguranca-run semana3-quatro-bracos

semana3-run-blindado:
	uv run --project backend python evals/runners/semana3_local.py --variante blindado --run-dir "$(RUN_DIR_BLINDADO)" --model "$(LOCAL_MODEL)" --embedding-model "$(EMBED_MODEL)" --dataset evals/datasets/golden_set_v2_consolidado.jsonl

seguranca-smoke:
	uv run --project backend python evals/runners/suite_seguranca.py --synthetic-smoke --fail-on-api-elim --saida-dir evals/reports/seguranca_smoke

seguranca-run:
	uv run --project backend python evals/runners/suite_seguranca.py --dataset evals/datasets/seguranca_variantes_v1.jsonl --provider ollama --model "$(LOCAL_MODEL)" --base-url http://localhost:11434 --timeout 180 --saida-dir "$(SEG_DIR)"

.PHONY: dast strix-local

dast:
	bash scripts/seguranca/dast.sh

strix-local:
	bash scripts/seguranca/strix_local.sh

semana3-quatro-bracos:
	uv run --project backend python evals/runners/consolidar_quatro_bracos.py --coleta-padrao "$(COLETA_PADRAO)" --coleta-blindada "$(RUN_DIR_BLINDADO)" --seguranca "$(SEG_DIR)/seguranca.json" --saida-dir "$(QUATRO_DIR)"

.PHONY: ragas-v2-reavaliar semana3-run-v3 semana3-run-blindado-v3 seguranca-run-v2 semana3-quatro-bracos-v3 guardrail-holdout

ragas-v2-reavaliar:
	@test -n "$(COLETA_DIR)" || (echo "Informe COLETA_DIR=<pasta da coleta>"; exit 1)
	uv run --project evals python evals/runners/avaliar_ragas_oficial.py --coleta-dir "$(COLETA_DIR)" --evaluator-model "$(LOCAL_MODEL)" --embedding-model "$(EMBED_MODEL)" --evaluation-name ragas_v2 --juiz ptbr_sem_citacao

semana3-run-v3:
	uv run --project backend python evals/runners/semana3_local.py --prompt-version semana3-v3 --juiz ptbr_sem_citacao --evaluation-name ragas_v2 --run-dir "$(RUN_DIR_V3)" --model "$(LOCAL_MODEL)" --embedding-model "$(EMBED_MODEL)" --dataset evals/datasets/golden_set_v2_consolidado.jsonl

semana3-run-blindado-v3:
	uv run --project backend python evals/runners/semana3_local.py --variante blindado --prompt-version semana3-v3 --juiz ptbr_sem_citacao --evaluation-name ragas_v2 --run-dir "$(RUN_DIR_BLINDADO_V3)" --model "$(LOCAL_MODEL)" --embedding-model "$(EMBED_MODEL)" --dataset evals/datasets/golden_set_v2_consolidado.jsonl

seguranca-run-v2:
	uv run --project backend python evals/runners/suite_seguranca.py --dataset evals/datasets/seguranca_variantes_v2.jsonl --regra-clinica "$(REGRA_CLINICA)" --provider ollama --model "$(LOCAL_MODEL)" --base-url http://localhost:11434 --timeout 180 --saida-dir "$(SEG_DIR_V2)"

semana3-quatro-bracos-v3:
	uv run --project backend python evals/runners/consolidar_quatro_bracos.py --coleta-padrao "$(RUN_DIR_V3)" --coleta-blindada "$(RUN_DIR_BLINDADO_V3)" --seguranca "$(SEG_DIR_V2)/seguranca.json" --saida-dir "$(QUATRO_DIR_V3)"

guardrail-holdout:
	@test -f "$(HOLDOUT)" || (echo "Holdout ausente: $(HOLDOUT). Siga evals/configs/protocolo_holdout_guardrail.md"; exit 1)
	uv run --project backend python evals/runners/guardrail_runner.py --dataset "$(HOLDOUT)" --alvo app.guardrails.clinical:deve_bloquear --max-falso-bloqueio 0.05 --relatorio holdout_camada1.json
	uv run --project backend python evals/runners/guardrail_runner.py --dataset "$(HOLDOUT)" --alvo app.guardrails.segunda_camada:deve_bloquear --max-falso-bloqueio 0.05 --relatorio holdout_camada2.json
	uv run --project backend python evals/runners/guardrail_runner.py --dataset "$(HOLDOUT)" --alvo app.guardrails.segunda_camada:deve_bloquear_combinado --max-falso-bloqueio 0.05 --relatorio holdout_combinado.json

docker-build:
	docker build -t sus-cidadao-backend:latest -f backend/Dockerfile .

clean:
	uv run --project backend python -c "import pathlib, shutil; root = pathlib.Path('.'); [shutil.rmtree(p, ignore_errors=True) for name in ('__pycache__', '.pytest_cache', '.ruff_cache', '.mypy_cache') for p in root.rglob(name) if '.venv' not in p.parts]; [p.unlink(missing_ok=True) for p in root.rglob('*.pyc') if '.venv' not in p.parts]"

S4_PILOT_DIR ?= evals/reports/semana4_piloto
S4_RUN_DIR ?= evals/reports/semana4_comparativo_v8
S4_RESULTADO ?= $(S4_RUN_DIR)/resultado.json
S4_EVAL_DIR ?= $(S4_RUN_DIR)/avaliacao
S4_MODELS ?= qwen3.5:4b
S4_EVAL_MODELS ?=
S4_EVAL_MODEL ?= qwen2.5:14b

.PHONY: demo-agents semana4-pilot semana4-compare semana4-eval
demo-agents:
	cd backend && uv run python -m app.agents.demo

semana4-pilot:
	uv run --project backend python evals/runners/semana4_comparativo.py --pilot --run-dir "$(S4_PILOT_DIR)" --models $(S4_MODELS)

semana4-compare:
	uv run --project backend python evals/runners/semana4_comparativo.py --run-dir "$(S4_RUN_DIR)" --models $(S4_MODELS)

semana4-eval:
	uv run --project evals python evals/runners/semana4_avaliacao.py --resultado "$(S4_RESULTADO)" --eval-dir "$(S4_EVAL_DIR)" --evaluator-model "$(S4_EVAL_MODEL)" --embedding-model "$(EMBED_MODEL)" $(if $(S4_EVAL_MODELS),--models $(S4_EVAL_MODELS),)

STT_PROVIDER ?= disabled
STT_MODEL ?= base

.PHONY: demo-multimodal eval-multimodal
demo-multimodal:
ifeq ($(STT_PROVIDER),faster_whisper)
	cd backend && uv run --with faster-whisper python -m app.agents.demo_multimodal --stt-provider "$(STT_PROVIDER)" --stt-model "$(STT_MODEL)" --summary
else
	cd backend && uv run python -m app.agents.demo_multimodal --stt-provider "$(STT_PROVIDER)" --stt-model "$(STT_MODEL)" --summary
endif

eval-multimodal:
ifeq ($(STT_PROVIDER),disabled)
	uv run --project backend python evals/runners/avaliar_multimodal.py --synthetic-smoke
else
	uv run --project backend --with faster-whisper python evals/runners/avaliar_multimodal.py --stt-provider "$(STT_PROVIDER)" --stt-model "$(STT_MODEL)"
endif

# Monitoramento: o MLflow fica fora do uv.lock (entra só nestes alvos, versão fixa).
# Ex.: make registrar-avaliacoes ROTULO=semana4-v3-2026-11-19 ARTEFATOS="--semana4 evals/reports/semana4_comparativo_v3/resultado.json"
.PHONY: registrar-avaliacoes mlflow-ui
registrar-avaliacoes:
	@test -n "$(ROTULO)" || (echo "Defina ROTULO=, ex.: ROTULO=semana4-2026-11-19" && exit 1)
	@test -n "$(ARTEFATOS)" || (echo "Defina ARTEFATOS=, ex.: ARTEFATOS=\"--seguranca pasta/seguranca.json\"" && exit 1)
	uv run --project backend --with "mlflow==$(MLFLOW_VERSAO)" python observability/registrar_avaliacoes.py --rotulo "$(ROTULO)" $(ARTEFATOS)

mlflow-ui:
	uv run --project backend --with "mlflow==$(MLFLOW_VERSAO)" mlflow ui --backend-store-uri sqlite:///evals/reports/mlflow.db --host 127.0.0.1 --port 5050
