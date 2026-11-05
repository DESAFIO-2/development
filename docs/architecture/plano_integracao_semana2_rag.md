# 📘 Plano de Integração e Manifesto Técnico — Semana 2 (RAG & Base de Conhecimento)

> **SUS Cidadão (NavegaSUS)** — *Challenge 2: Qualidade de Vida e Tomada de Decisão com IA*  
> **Instituto Eldorado | Residência em Inteligência Artificial (UnB / Softex / MCTI)**  
> **Autor / Tech Lead:** Samuel de Souza Rodrigues | **Squad:** Mickeias Paiva, Marlon Marques, Jhiovana Ribeiro, Tayrine Zitkoski  
> **Data:** 2026-11-05

---

## 1. Visão Geral e Objetivo deste Documento

Este documento consolida **todo o contexto técnico, decisões de arquitetura, levantamento de dados e regras de engenharia** acumulados durante a Semana 2 do projeto. Ele serve como **fonte única de verdade (Single Source of Truth - SSOT)** para o squad e para orientar qualquer nova sessão de desenvolvimento ou agente de IA.

---

## 2. A Régua dos Mentores (Entregável da Semana 2)

* **Prazo de Entrega:** Segunda-feira (09/11/2026), às 08h00.
* **Canal de Envio:** Pasta da equipe no Microsoft Teams, canal *Segundo Desafio*.
* **Diretriz Central do Edital:**  
  > *"Nesta etapa, o foco é a qualidade da recuperação de informação, a fundamentação das respostas e a rastreabilidade das fontes, não a interface ou experiência do usuário."*

### Matriz de Requisitos da Banca

| Bloco | Requisito Formal | Como Atendemos no SUS Cidadão |
| :--- | :--- | :--- |
| **Artefatos** | **1. Base de conhecimento curada** | Catálogo oficial RENAME 2024, Farmácia Popular, REME-DF 2026, Protocolos SES-DF e estoque CEAF. |
| **Artefatos** | **2. Mínimo de 20 documentos-fonte** | 14 fontes institucionais mapeadas (`levantamento-fontes.md`) + 42 chunks normativos rastreados com SHA-256. |
| **Artefatos** | **3. Descrição da estratégia de chunking** | Chunking semântico estruturado por artigo/seção de portaria (512 tokens / overlap 64) com metadados ricos de linhagem. |
| **Artefatos** | **4. Descrição da estratégia de embeddings** | Embeddings multilíngues densos (`bge-m3` / `all-MiniLM-L6-v2`) com métrica de similaridade cosseno (`hnsw:space: cosine`). |
| **Artefatos** | **5. Implementação de banco vetorial** | ChromaDB multi-coleção persistente em disco (`data/vectorstore/`) com coleções especializadas. |
| **Demonstração** | **6. Consulta submetida ao sistema** | Caso de teste real da Persona Dona Helena (Ceilândia) e Lucas (Taguatinga). |
| **Demonstração** | **7. Chunks mais relevantes (Top-K)** | Exibição transparente dos Top-K chunks com score de similaridade e metadados de procedência. |
| **Demonstração** | **8. Resposta fundamentada no conteúdo** | Síntese cidadã acolhedora ancorada estritamente no contexto recuperado, eliminando alucinações. |
| **Demonstração** | **9. Evidência das fontes utilizadas** | Citação formal do número da portaria, artigo, data de vigência e hash do manifesto oficial. |
| **Documentação**| **10. Diagrama de arquitetura** | Diagrama de fluxo de dados ponta a ponta em [fluxo_de_dados_arquitetura.md](fluxo_de_dados_arquitetura.md). |
| **Documentação**| **11. Pipeline de ingestão de dados** | Documentação e código executável de ingestão, chunking e indexação em `backend/app/ingestion/`. |

---

## 3. Raio-X do Trabalho de Ciência de Dados (`DESAFIO-2/Data-Science`)

O Cientista de Dados Marlon Marques desenvolveu uma base sólida no repositório [DESAFIO-2/Data-Science](https://github.com/DESAFIO-2/Data-Science.git) sob a metodologia **Spec-Driven Development (SDD)**:

### 3.1. Especificações Técnicas (Specs SDD)
* `SPEC-00`: Contratos Silver/Gold, manifesto SHA-256 e governança MLflow;
* `SPEC-01`: Sincronização criptográfica e Análise Exploratória de Dados (EDA);
* `SPEC-02`: Golden Dataset (16 casos auditados: Dona Helena, Lucas, casos fora de elenco e bloqueio clínico);
* `SPEC-03`: Calibração matemática de abstenção — provou que o limiar inicial `0.12` era vulnerável e calibrou o corte ótimo para `min_score = 0.18` (atingindo F1 = 1.0000);
* `SPEC-04`: Benchmark científico comparando LLM pura vs. RAG TF-IDF vs. RAG Híbrido;
* `SPEC-05`: Orquestrador de 4 agentes especializados + Guardrails LGPD e Ato Médico;
* `SPEC-06`: Integração com a API Power BI do InfoSaúde-DF (estoque em tempo real do Alto Custo e geolocalização de farmácias);
* `SPEC-07`: Indexação multi-coleção no ChromaDB (`ceaf_live_stock`, `df_pharmacies`, `sus_normative_protocols`);
* `SPEC-08`: Pipeline unificado de PDFs, conversão JSON->PDF com ReportLab e extração textual via `pypdf`.

### 3.2. Dados Estruturados Prontos
1. `data/gold/medicamentos_sus_canonical.json`: 24 apresentações essenciais com DCB, concentração, componente RENAME, gratuidade PFPB, exigência de LME e validade de receita;
2. `data/gold/ceaf_live_stock.json`: **857 registros reais de estoque** das 3 farmácias de Alto Custo do DF (Asa Sul, Ceilândia e Gama);
3. `data/gold/df_pharmacies_geolocated.json`: **231 estabelecimentos de saúde do DF** com coordenadas geográficas, endereços e links do Google Maps;
4. `data/silver/normative_chunks.json`: 42 chunks normativos rastreados;
5. `specs/levantamento-fontes.md`: 14 fontes institucionais detalhadas (F01 a F14).

---

## 4. Manifesto de Portação & Regras de Engenharia (Padrão Big Tech)

Para integrar esse material no repositório corporativo `DESAFIO-2/development`, as seguintes regras são obrigatórias:

### Regra 1: Respeito Incondicional à Clean Architecture (Zero "Copy & Paste" Cego)
* O código em `Data-Science` é projetado como uma CLI monolítica experimental (`sus_cidadao_ds`).
* No `development`, os componentes devem ser desacoplados em camadas:
  * **Domínio (`domain/`):** Modelos puros (`Medication`, `Prescription`, `AccessRoute`, `StockAvailability`);
  * **Portas (`application/ports/`):** Interfaces abstratas (`VectorStorePort`, `HybridRetrieverPort`);
  * **Infraestrutura (`infrastructure/`):** Adaptador concreto do ChromaDB (`infrastructure/vectorstores/chroma.py`);
  * **Casos de Uso (`application/use_cases/`):** `AuditPrescriptionUseCase` orquestra as regras sem saber os detalhes do ChromaDB.

### Regra 2: Integridade Criptográfica Medallion (`data/`)
* Todos os arquivos de dados copiados devem manter os hashes SHA-256 correspondentes no catálogo oficial `data/manifests/manifest.json`;
* O diretório binário `data/vectorstore/` é estritamente ignorado no Git (`.gitignore`) e gerado por scripts de compilação.

### Regra 3: Conformidade com o Quality Gate de CI/CD da Tayrine
* O arquivo `golden_set_v1.json` deve ser convertido para `evals/datasets/golden_set_v1.jsonl`, contendo obrigatoriamente a chave `"id"` única por linha;
* Deve passar sem erros pelo validador `evals/runners/validar_datasets.py` executado no CI.

### Regra 4: Tipagem Estrita e Zero Erros no Mypy/Ruff
* Todas as classes portadas devem conter `from __future__ import annotations` e anotações completas de tipos;
* Todo commit deve manter verdes os comandos:
  ```bash
  uv run ruff check .
  uv run ruff format --check .
  uv run mypy app tests
  uv run pytest
  ```

---

## 5. Mapeamento de Arquivos: De `Data-Science` para `development`

| Origem (`Data-Science`) | Destino Adaptado (`development`) | Camada Arquitetural |
| :--- | :--- | :--- |
| `data/gold/medicamentos_sus_canonical.json` | `data/processed/medicamentos_sus_canonical.json` | Camada de Dados Gold |
| `data/gold/ceaf_live_stock.json` | `data/processed/ceaf_live_stock.json` | Camada de Dados Gold |
| `data/gold/df_pharmacies_geolocated.json` | `data/processed/df_pharmacies_geolocated.json` | Camada de Dados Gold |
| `data/silver/normative_chunks.json` | `data/processed/normative_chunks.json` | Camada de Dados Silver |
| `data/manifests/manifest.json` | `data/manifests/manifest.json` | Governança & Hashes |
| `src/sus_cidadao_ds/retrieval/chroma_indexer.py` | `backend/app/infrastructure/vectorstores/chroma.py` | Infraestrutura (Adapter) |
| `src/sus_cidadao_ds/retrieval/retrievers.py` | `backend/app/retrieval/hybrid_retriever.py` | Recuperação & Domínio |
| `src/sus_cidadao_ds/guardrails/pii_masker.py` | `backend/app/guardrails/pii.py` | Segurança LGPD |
| `src/sus_cidadao_ds/guardrails/clinical_blocker.py`| `backend/app/guardrails/clinical.py` | Segurança Ato Médico |
| `evals/datasets/golden_set_v1.json` | `evals/datasets/golden_set_v1.jsonl` | Avaliação e Golden Sets |
| `evals/runners/` (Benchmark) | `evals/runners/demo_rag_runner.py` | Demonstração da Banca |
| `specs/levantamento-fontes.md` | `docs/data_sources/catalogo_fontes_oficiais.md` | Documentação de Fontes |

---

## 6. Prompt Instrucional para Nova Sessão / Agente de IA

Se você estiver abrindo uma nova sessão em outro dispositivo, envie o seguinte prompt inicial:

```text
Olá! Estou continuando o projeto SUS Cidadão (NavegaSUS) no repositório DESAFIO-2/development.
Por favor, leia atentamente os seguintes documentos antes de executar qualquer ação:
1. docs/architecture/plano_integracao_semana2_rag.md (Plano de Integração e Regras de Engenharia);
2. docs/adr/0003_estrategia_avaliacao_metricas_ragas.md (Decisão sobre RAGAS vs BLEU/ROUGE);
3. docs/architecture/matriz_metricas_avaliacao.md (Critérios de corte de avaliação);
4. README.md (Estrutura do repositório e roadmap).

Nosso objetivo imediato é executar a portação limpa dos dados e componentes do repositório DESAFIO-2/Data-Science para o development, respeitando a Clean Architecture e preparando o entregável da Semana 2 para segunda-feira às 8h00.
```
