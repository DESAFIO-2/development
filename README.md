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
| **Comparação LLM sem recuperação × LLM com RAG** | Semana 3 | Protocolo corrigido; avaliação real pendente | [Entregável Semana 3](docs/entregaveis_semana3_comparativo.md) e [Auditoria](docs/auditoria_semana3.md) |
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
│   ├── adr/                     # Architecture Decision Records (ADRs 0001, 0002 e 0003)
│   ├── architecture/            # Diagramas C4, Matriz de Métricas e Especificação RAG Semana 2
│   ├── pdr_semana1/             # Documento de Definição de Produto e Requisitos aprovado
│   ├── data_sources/            # Dicionários de dados das fontes oficiais
│   ├── runbooks/                # Procedimentos de execução e incidentes
│   └── security/                # Modelo de ameaças e conformidade LGPD
├── evals/                       # Suíte Contínua de LLMOps e Métricas RAGAS
│   ├── datasets/                # Datasets rotulados (Guardrail Clínico v1 e Golden Set)
│   ├── metrics/                 # Métricas de Faithfulness, Answer Relevancy, Context Recall
│   ├── runners/                 # Runners de benchmark automatizados (guardrail_runner.py)
│   ├── configs/                 # Configurações de parâmetros de chunking/top_k
│   ├── baselines/               # Linhas de base comparativas (Palavras-chave, LLM pura)
│   └── reports/                 # Relatórios consolidados de avaliação
├── observability/               # Instrumentação de telemetria, tracing e latência
├── CONTRIBUTING.md              # Guia de contribuição e GitFlow do squad
├── SECURITY.md                  # Política de segurança e proteção de dados de saúde
├── Makefile                     # Atalhos operacionais (make test, make run-api, make lint, make eval)
└── README.md
```

---

## Comandos Rápidos

```bash
# 1. Instalar dependências (via uv no backend)
make dev-install

# 2. Executar suíte de testes do backend
make test

# 3. Executar linter e checagem de tipos
make lint

# 4. Iniciar API FastAPI local
make run-api

# 5. Executar suíte de avaliações e guardrails éticos
make eval

# 6. Demonstrador Oficial da Semana 2 (Dona Helena e Lucas Mendes)
make demo

# 7. Benchmark determinístico (Golden Set v1 por padrão)
make benchmark
make benchmark DATASET=evals/datasets/golden_set_v2_consolidado.jsonl

# 8. Smoke offline do protocolo (não mede desempenho de LLM)
make compare-smoke DATASET=evals/datasets/golden_set_v2_consolidado.jsonl
```

### Endpoints Principais da API (FastAPI)

- `GET /health` — Verificação de prontidão do sistema e telemetria básica.
- `GET /api/v1/medications/autocomplete?q=losartana` — Autocomplete assistido de fármacos da RENAME com princípios ativos DCB.
- `POST /api/v1/prescriptions/audit` — Auditoria normativa de receitas médicas, mascaramento LGPD, roteiro de gratuidade e preservação do Ato Médico.

