SUS Cidadão (NavegaSUS)
> **Apoio Inteligente à Tomada de Decisão para Acesso Gratuito a Medicamentos e Exames no SUS**  
> *Challenge 2: Qualidade de Vida e Tomada de Decisão com IA* — **Instituto Eldorado | Residência em Inteligência Artificial (UnB / Softex)**
---
## Sobre o Projeto
Milhões de famílias brasileiras comprometem parte expressiva de sua renda adquirindo medicamentos de uso contínuo no varejo privado por puro desconhecimento das regras públicas de gratuidade. 

O **SUS Cidadão** é uma solução de Inteligência Artificial desenhada para empoderar o paciente da rede pública e seus cuidadores familiares. A partir do **preenchimento assistido com autocomplete dos medicamentos**, **digitalização da receita médica na Carteira Digital (RF08)** e **mensagem de voz com a localidade (RA)**, o sistema audita as regras oficiais do Ministério da Saúde e do Distrito Federal, entregando um roteiro prático e auditável:
1. **Onde retirar gratuitamente:** Diferenciação automática entre *Farmácia Popular* (drogaria privada com CPF), *Unidade Básica de Saúde - UBS* (Atenção Primária) e *Farmácia de Alto Custo* (Componente Especializado via processo LME).
2. **Checklist Documental e SISREG:** Documentos obrigatórios e critérios de regulação para consultas e exames especializados.
3. **Gestão da Receita e Validade:** Carteira digital no app com contagem regressiva e alertas preventivos a 15 e 7 dias antes do vencimento.
4. **Guardrail Ético Inegociável:** Atuação estritamente restrita à **navegação administrativa e cidadã**, sem realizar prescrição clínica, diagnóstico ou troca de remédios.
---
## Arquitetura Técnica & Roadmap (7 Semanas)

  

[ Usuário ] ──> (PDF / Imagem / Áudio)
│
▼
[ Pipeline Multimodal ]  ──>  Desidentificação LGPD (PII Masking)
│
▼
[ Orquestrador Multiagentes ]
├── 1. Agente Extrator & Triador Multimodal
├── 2. Agente Auditor Farmacêutico (RAG: RENAME 2024 + Farmácia Popular + REME-DF)
├── 3. Agente Consultor SISREG / SES-DF (RAG: Protocolos CPPAS)
└── 4. Agente Sintetizador do Roteiro Cidadão
│
▼
[ Painel de Apoio à Decisão & Gestão da Receita ]


  
* **Semana 1:** Definição do Problema, Personas, Stakeholders, Riscos e Métricas (PDR ABNT).
* **Semana 2:** Base de Conhecimento e Recuperação (RAG Híbrido: CSV tabular + Chunks vetoriais de portarias).
* **Semana 3:** Avaliação Experimental Científica (LLM pura vs. RAG com framework RAGAS).
* **Semana 4:** Sistema Multiagentes Colaborativo (LangGraph / CrewAI).
* **Semana 5:** Pipeline Multimodal (PDFs digitais padrão CFM/ICP-Brasil + OCR + Transcrição Whisper).
* **Semana 6:** Integração Sistêmica Ponta a Ponta (API FastAPI + Interface).
* **Semana 7:** Bateria de Testes com Usuários, Métricas DCS e Demonstração Final.

---

## Status de Entregas & Maturidade Técnica

| Componente | Fase / Semana | Status | Artefato de Referência |
| :--- | :--- | :--- | :--- |
| **Arquitetura & Clean Architecture** | Semana 1 | ✅ Concluído | [ADR 0001](docs/adr/0001_enterprise_clean_architecture_and_rag.md) e `backend/app/` |
| **Decisão sobre cliente mobile & carteira digital** | Semana 1 | ✅ Documentada | [ADR 0002](docs/adr/0002_mobile_first_react_native_client.md) |
| **Estratégia de Avaliação & Métricas** | Semanas 1-2 | ✅ Concluído | [ADR 0003](docs/adr/0003_estrategia_avaliacao_metricas_ragas.md) e [Matriz de Métricas](docs/architecture/matriz_metricas_avaliacao.md) |
| **Dataset de Guardrails Clínicos** | Semana 2 | ✅ Concluído | `evals/datasets/guardrail_clinico_v1.jsonl` (Recall: 100%, Falso Bloqueio: 0%) |
| **Ingestão Tabular RENAME / PFPB** | Semana 2 | ✅ Concluído | Catálogo Canônico RENAME Integral (992 apresentações / 575 DCBs), Estoque CEAF (857 itens), Farmácias DF (228 pontos) |
| **Recuperação híbrida na API** | Semanas 2–3 | ✅ Implementada | DCB, BM25 e TF-IDF com RRF. Catálogo consolidado v5 com 1.787 registros. |
| **Benchmark determinístico / Golden Dataset** | Semanas 2–3 | ✅ v1 e v2 aprovados no benchmark atual | [Registro da portação v5](docs/implementation/plano_semana3_corpus_v5.md) |
| **Comparação LLM sem recuperação × LLM com RAG** | Semana 3 | ✅ Protocolo desacoplado, validado e pronto para execução local (M4) | [Entregável Semana 3](docs/entregaveis_semana3_comparativo.md), [ADR 0004](docs/adr/0004_integridade_comparativo_semana3.md) e [Roteiro MacBook M4](docs/implementation/plano_execucao_semana3_local_macbook.md) |
| **Multiagentes Especializados** | Semana 4 | ⏳ Planejado | Orquestração LangGraph / CrewAI sobre Casos de Uso |
| **Interface Mobile & Acessibilidade** | Semanas 5-6 | ⏳ Planejado | App React Native com gravação de áudio e notificações |
| **Validação com Usuários & DCS** | Semana 7 | ⏳ Planejado | Redução de Conflito Decisório ($\ge 35\%$) com voluntários |
---
## Bases de Dados Oficiais (100% Públicas)
* **RENAME 2024:** Relação Nacional de Medicamentos Essenciais (Portaria GM/MS nº 6.324/2024).
* **Programa Farmácia Popular do Brasil:** Elenco oficial de gratuidade expandida do Ministério da Saúde.
* **REME-DF:** Relação de Medicamentos do Distrito Federal (SES-DF).
* **SISREG III / CPPAS:** Protocolos de Encaminhamento e Regulação Ambulatorial da SES-DF e Ministério da Saúde.
---
## Squad
| Papel | Responsável |
| :--- | :--- |
| **Engenheiro de IA** | Samuel de Souza Rodrigues |
| **Arquiteto de Software** | Mickeias Charles de Oliveira Paiva |
| **Cientista de Dados** | Marlon Dias Marques |
| **Engenheira de Dados** | Jhiovana Silva Ribeiro |
| **MLOps / LLMOps** | Tayrine Hevellin Zitkoski |

---

## Estrutura do Repositório (Clean Architecture & LLMOps Monorepo)

```text
challenge2/
├── .github/
│   ├── workflows/backend-ci.yml # CI automatizado (Ruff, Mypy, Pytest, Docker)
│   └── CODEOWNERS               # Matriz de responsabilidade de revisão por componente
├── backend/                     # Aplicação e Serviços de IA (FastAPI + Clean Architecture)
│   ├── app/
│   │   ├── main.py              # Entrypoint da API FastAPI
│   │   ├── core/                # Configurações globais e logs estruturados
│   │   ├── api/                 # Rotas HTTP (/health, /audit-prescription)
│   │   ├── domain/              # Modelos e regras de negócio puras (Prescription, Guidance)
│   │   ├── application/         # Casos de uso e portas abstratas (Clean Architecture)
│   │   │   ├── use_cases/       # AuditPrescription, SearchMedication, ClassifyRoute
│   │   │   ├── ports/           # Interfaces para repositórios e provedores
│   │   │   └── services/        # Orquestração do fluxo de auditoria
│   │   ├── infrastructure/      # Adaptadores concretos (ChromaDB, Embeddings, LLM)
│   │   ├── ingestion/           # Pipelines de ETL e normalização DCB (Engenharia de Dados)
│   │   ├── retrieval/           # Hybrid Retriever: Busca Tabular (DCB) + Vetorial (Portarias)
│   │   └── guardrails/          # Mascaramento PII (LGPD) e bloqueio clínico (Preservação do Ato Médico)
│   ├── tests/                   # Testes automatizados (test_health, unitários e integração)
│   ├── Dockerfile               # Containerização com usuário não-root e healthcheck
│   ├── pyproject.toml           # Dependências gerenciadas via uv
│   └── uv.lock
├── data/                        # Dados e Governança de Linhagem
│   ├── manifests/               # Linhagem, datas de publicação e hashes (RENAME, PFPB, REME-DF, SISREG)
│   ├── raw/                     # Arquivos públicos originais baixados
│   ├── staging/                 # Dados intermediários de transformação
│   ├── processed/               # Tabelas canônicas limpas (medicamentos_sus_canonical)
│   └── vectorstore/             # Índices ChromaDB locais (ignorado no Git)
├── docs/                        # Documentação Técnica e Decisões
│   ├── adr/                     # Architecture Decision Records (ADRs 0001, 0002, 0003 e 0004)
│   ├── architecture/            # Diagramas C4, Matriz de Métricas e Especificação RAG
│   ├── pdr_semana1/             # Documento de Definição de Produto e Requisitos aprovado
│   ├── data_sources/            # Dicionários de dados das fontes oficiais
│   ├── runbooks/                # Procedimentos de execução, portações e diretrizes de integridade para IA
│   ├── implementation/          # Roteiro de execução M4, curadoria e relatórios de validação
│   └── security/                # Modelo de ameaças e conformidade LGPD
├── evals/                       # Suíte Contínua de LLMOps e Métricas RAGAS
│   ├── datasets/                # Datasets rotulados (Guardrail Clínico v1, Golden Set v1 e v2)
│   ├── metrics/                 # Definições formais das métricas ADR 0003
│   ├── runners/                 # Runners desacoplados (coleta, checkpoints, RAGAS oficial, auditoria factual)
│   ├── ollama/                  # Modelfile congelado com contexto 8192, temp 0 e seed 42
│   ├── baselines/               # Fixtures offline para smoke tests sintéticos
│   ├── tests/                   # Testes de contrato de transporte e integração RAGAS
│   ├── pyproject.toml           # Ambiente isolado de avaliação (ragas==0.4.3, sem poluir a API)
│   ├── uv.lock                  # Lockfile independente de evals
│   └── reports/                 # Relatórios consolidados, checkpoints e auditorias (ignorado no Git)
├── observability/               # Instrumentação de telemetria, tracing e latência
├── CONTRIBUTING.md              # Guia de contribuição e GitFlow do squad
├── SECURITY.md                  # Política de segurança e proteção de dados de saúde
├── Makefile                     # Atalhos operacionais (make test, make run-api, make lint, make eval)
└── README.md
```

---

## Comandos Rápidos

```bash
# 1. Instalar dependências da API (uv no backend) e ambiente isolado de avaliação
make dev-install
make eval-setup

# 2. Executar suíte completa de testes do backend e contrato RAGAS
make test
make eval-test

# 3. Executar linter e checagem de tipos estrita
make lint
make format

# 4. Iniciar API FastAPI local
make run-api

# 5. Executar validação de datasets e guardrails éticos
make eval

# 6. Demonstrador Oficial RAG (Dona Helena e Lucas Mendes)
make demo

# 7. Benchmark determinístico (Golden Set v1 e v2)
make benchmark
make benchmark DATASET=evals/datasets/golden_set_v2_consolidado.jsonl

# 8. Smoke offline do protocolo comparativo (teste de encanamento sem custo de LLM)
make compare-smoke DATASET=evals/datasets/golden_set_v2_consolidado.jsonl

# 9. Execução Experimental Semana 3 no MacBook M4 (Ollama local: semana3-qwen14 + bge-m3)
make semana3-pilot     # Piloto rápido de 2 casos para verificar hardware e contexto
make semana3-run       # Coleta pareada (22 casos) + RAGAS oficial desacoplado com checkpoints
make semana3-finalize  # Consolidação offline após auditoria factual humana
```

### Endpoints Principais da API (FastAPI)

- `GET /health` — Verificação de prontidão do sistema e telemetria básica.
- `GET /api/v1/medications/autocomplete?q=losartana` — Autocomplete assistido de fármacos da RENAME com princípios ativos DCB.
- `POST /api/v1/prescriptions/audit` — Auditoria normativa de receitas médicas, mascaramento LGPD, roteiro de gratuidade e preservação do Ato Médico.

---

## Protocolo de Avaliação da Semana 3 (LLM pura vs. RAG)

Seguindo o [ADR 0004](docs/adr/0004_integridade_comparativo_semana3.md) e as [Diretrizes de Integridade de IA](docs/runbooks/diretrizes_integridade_ia.md), o comparativo opera em dois estágios rigorosamente desacoplados:

1. **Estágio 1 — Coleta Pareada (`evals/runners/comparar_semana3.py`):**
   - Executa os 22 casos do `golden_set_v2_consolidado.jsonl` em dois braços: sem recuperação vs. com RAG híbrido (`top_k=3`).
   - Cada chamada é persistida com checkpoints atômicos (`evals/runners/collection_checkpoint.py`), vinculados ao hash SHA-256 do código, dataset e modelo.
   - Respostas truncadas (`done_reason: length`) são invalidadas (`RESPOSTA_TRUNCADA`) e controles determinísticos de segurança (bloqueio clínico e abstenção) são segregados (`CONTROLE_DETERMINISTICO`) das inferências puras de modelo (`PAR_LLM`).

2. **Estágio 2 — Avaliação RAGAS Oficial & Auditoria Factual (`evals/runners/avaliar_ragas_oficial.py`):**
   - Utiliza a biblioteca oficial `ragas==0.4.3` isolada em `evals/pyproject.toml` (sem contaminação do ambiente de produção da API).
   - Calcula formalmente as metas do [ADR 0003](docs/adr/0003_estrategia_avaliacao_metricas_ragas.md): `Faithfulness` ($\ge 0{,}92$, medido exclusivamente sobre o contexto recuperado do RAG), `Answer Relevancy` ($\ge 0{,}88$), `Context Recall` ($\ge 0{,}90$) e `Context Precision` ($\ge 0{,}88$).
   - Acompanha ficha de auditoria factual independente (`auditoria_factual_humana.json`) com vinculação criptográfica e separação estrita de denominadores para aferição de alucinações normativas reais, sem métricas sintéticas.
   - Permite consolidação offline instantânea via `make semana3-finalize`.

