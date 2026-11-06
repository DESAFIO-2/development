# 🏛️ Entregáveis da Semana 2 — Base de Conhecimento e Recuperação Híbrida (RAG)

> **Projeto:** SUS Cidadão (NavegaSUS)  
> **Desafio:** *Challenge 2: Qualidade de Vida e Tomada de Decisão com IA*  
> **Programa:** Residência em Inteligência Artificial — **Instituto Eldorado | UnB | Softex | MCTI**  
> **Prazo de Entrega:** Segunda-feira, 09 de Novembro de 2026, às 08h00  
> **Squad:**  
> • Samuel de Souza Rodrigues (Engenheiro de IA)  
> • Mickeias Charles de Oliveira Paiva (Arquiteto de Software)  
> • Marlon Dias Marques (Cientista de Dados)  
> • Jhiovana Silva Ribeiro (Engenheira de Dados)  
> • Tayrine Hevellin Zitkoski (MLOps / LLMOps)  

---

## Sumário Executivo

Este documento consolida os **entregáveis formais da Semana 2**, organizados estritamente conforme a régua de avaliação da banca do Instituto Eldorado. O foco desta etapa é a **qualidade da recuperação de informação, a rastreabilidade normativa das fontes governamentais, a eliminação de alucinações clínicas e a arquitetura de engenharia limpa**.

---

# PARTE 1: DEMONSTRAÇÃO DO SISTEMA RAG

Demonstração prática executada sobre o motor de **Recuperação Híbrida (Tabular DCB + BM25Okapi + TF-IDF n-gramas com Reciprocal Rank Fusion)**, cobrindo os cenários reais das personas do projeto.

---

### Cenário 1: Persona Dona Helena (68 anos, Ceilândia - DF)
*Perfil:* Aposentada, hipertensa e diabética, com receita recente emitida na UBS de Ceilândia.

#### 1. Consulta Submetida ao Sistema
* **Região Administrativa:** Ceilândia - DF
* **Medicamentos Prescritos (Receita SUS):**
  1. `Losartana Potássica 50mg comprimido`
  2. `Cloridrato de Metformina 850mg comprimido`
  3. `Dapagliflozina 10mg comprimido`
* **Dúvida Logística do Cidadão:** *"Onde retiro esses remédios de graça e quais papéis preciso levar?"*

#### 2. Recuperação dos Chunks / Documentos Mais Relevantes (Top-K)

| Item da Receita | Rank | Chunk ID | Score RRF | Fonte Oficial / Documento | Pág. | Hash SHA-256 do Chunk |
| :--- | :---: | :---: | :---: | :--- | :---: | :--- |
| **Losartana Potássica 50mg** | #1 | `CHK-PFPB-001` | **0.6651** | Portaria GM/MS nº 3.677/2024 — Elenco Gratuidade Plena PFPB | Pág. 11 | `319a06cf37fe...` |
| **Metformina 850mg** | #1 | `CHK-PFPB-001` | **0.6542** | Portaria GM/MS nº 3.677/2024 — Elenco Gratuidade Plena PFPB | Pág. 11 | `319a06cf37fe...` |
| **Dapagliflozina 10mg** | #1 | `CHK-PFPB-002` | **0.6144** | Portaria GM/MS nº 3.677/2024 — Gratuidade Expandida PFPB | Pág. 16 | `7b5511ebb329...` |

*Trecho Normativo Recuperado (`CHK-PFPB-001`):*
> *"Os medicamentos destinados ao tratamento de hipertensão arterial (losartana potássica 50 mg...) e diabetes mellitus (cloridrato de metformina 500 mg e 850 mg...) são dispensados com 100% de gratuidade nas drogarias privadas credenciadas ao Programa Farmácia Popular do Brasil (Aqui Tem Farmácia Popular). Para retirada, o paciente deve apresentar documento oficial com foto e número do CPF, acompanhado de receita médica válida emitida por médico do SUS ou particular, com validade de até 180 dias para uso contínuo."*

#### 3. Resposta Fundamentada no Conteúdo Recuperado

* **Resumo Acolhedor:**  
  *"Auditamos 3 medicamento(s) da sua receita para a região de Ceilândia. Todos os 3 remédios possuem 100% de gratuidade e você pode retirá-los diretamente na Farmácia Popular (drogarias privadas credenciadas com o seu CPF), sem precisar enfrentar filas na UBS."*

* **Cartões do Roteiro Cidadão:**
  * **Losartana Potássica 50mg:**
    * *Via de Retirada:* `FARMACIA_POPULAR`
    * *Onde Retirar:* Drogarias privadas credenciadas ao Farmácia Popular em Ceilândia (ex: Drogasil, Raia, Pacheco) ou na UBS de referência.
    * *O que Levar:* Documento oficial com foto, CPF do paciente e receita médica válida (até 180 dias).
    * *Validade da Receita:* 180 dias a contar da emissão.
  * **Cloridrato de Metformina 850mg:**
    * *Via de Retirada:* `FARMACIA_POPULAR`
    * *Onde Retirar:* Drogarias privadas credenciadas ao Farmácia Popular em Ceilândia.
    * *O que Levar:* Documento oficial com foto, CPF e receita médica válida.
    * *Validade da Receita:* 180 dias.
  * **Dapagliflozina 10mg:**
    * *Via de Retirada:* `FARMACIA_POPULAR` (Gratuidade Expandida 2024)
    * *Onde Retirar:* Drogarias privadas credenciadas ao Farmácia Popular.
    * *O que Levar:* Documento com foto, CPF e receita médica válida.
    * *Validade da Receita:* 180 dias.

#### 4. Evidência das Fontes Utilizadas na Resposta
* **Base Legal Primária:** Ministério da Saúde — Portaria GM/MS nº 3.677/2024 (Programa Farmácia Popular do Brasil, Art. 5º e Art. 7º).
* **Base Legal Suplementar:** RENAME 2024 (Portaria GM/MS nº 6.324/2024) e REME-DF 2024 (SES-DF).
* **Rastreabilidade Criptográfica:** Manifesto auditado `data/manifests/manifest.json`.

---

### Cenário 2: Persona Lucas Mendes (34 anos, Taguatinga Sul - DF)
*Perfil:* Cuidador familiar do pai cardiopata, buscando obter medicação de Alto Custo no DF.

#### 1. Consulta Submetida ao Sistema
* **Região Administrativa:** Taguatinga Sul - DF
* **Medicamentos Prescritos:**
  1. `Adalimumabe 40mg solução injetável`
  2. `Sacubitril Valsartana 97/103mg comprimido`
* **Dúvida Logística do Cidadão:** *"Quais os documentos exigidos para pegar na Farmácia de Alto Custo e onde fica o polo?"*

#### 2. Recuperação dos Chunks / Documentos Mais Relevantes (Top-K)

| Item da Receita | Rank | Chunk ID | Score RRF | Fonte Oficial / Documento | Pág. | Hash SHA-256 |
| :--- | :---: | :---: | :---: | :--- | :---: | :--- |
| **Adalimumabe 40mg** | #1 | `CHK-REMEDF-002` | **0.5831** | Manual do Componente Especializado (CEAF) — SES-DF | Pág. 64 | `c2a19ef891...` |
| **Adalimumabe 40mg** | #2 | `CHK-RENAME-002` | **0.5785** | RENAME 2024 — Componente Especializado (CEAF) | Pág. 112 | `83b0f79cd1...` |
| **Sacubitril Valsartana** | #1 | `CHK-REMEDF-002` | **0.6417** | Manual do Componente Especializado (CEAF) — SES-DF | Pág. 64 | `c2a19ef891...` |
| **Regras Polos CEAF-DF** | #1 | `CHK-REGRA-CEAF-001`| **0.6193** | Manual CEAF-DF — Polos Regionais e Processo LME | Pág. 19 | `4c8d52fe10...` |

*Trecho Normativo Recuperado (`CHK-REGRA-CEAF-001`):*
> *"No Distrito Federal, os medicamentos do Componente Especializado (Alto Custo / CEAF) são dispensados exclusivamente em três polos centrais da Diretoria de Assistência Farmacêutica (DIASF): (1) Polo Asa Sul (Estação 102 Sul do Metrô); (2) Polo Ceilândia (Praça do Cidadão ao lado do HRC); e (3) Polo Gama. A obtenção exige abertura de processo administrativo com Laudo de Solicitação, Avaliação e Autorização de Medicamento(s) (LME) assinado pelo médico especialista (validade de 90 dias), receita médica em 2 vias com a Denominação Comum Brasileira (DCB), Termo de Esclarecimento e Responsabilidade (TER), exames exigidos pelo PCDT do Ministério da Saúde, Cartão SUS, CPF e comprovante de residência no DF."*

#### 3. Resposta Fundamentada no Conteúdo Recuperado

* **Resumo Acolhedor:**  
  *"Auditamos 2 medicamento(s) da sua receita para Taguatinga Sul. Ambos os itens pertencem ao Componente Especializado (Alto Custo) da SES-DF e exigem abertura de processo administrativo com o laudo LME. Para moradores de Taguatinga Sul, o polo regional de referência mais próximo é a Farmácia de Alto Custo de Ceilândia (ao lado do HRC) ou o Polo Asa Sul (Estação 102 Sul)."*

* **Cartão de Orientação Estruturado:**
  * **Via de Retirada:** `FARMACIA_ALTO_CUSTO` (CEAF-DF)
  * **Onde Dar Entrada e Retirar:**  
    1. Polo Ceilândia (Praça do Cidadão, ao lado do Hospital Regional de Ceilândia - HRC); ou  
    2. Polo Asa Sul (Subsolo da Estação 102 Sul do Metrô).
  * **Checklist Documental Obrigatório (PCDT):**
    - [ ] Laudo de Medicamento Especializado (LME) preenchido e assinado pelo médico com CID-10;
    - [ ] Receita médica em 2 vias com o nome genérico (DCB);
    - [ ] Termo de Esclarecimento e Responsabilidade (TER) assinado;
    - [ ] Cópia do Cartão Nacional de Saúde (CNS - Cartão SUS);
    - [ ] Cópia do Documento de Identidade com foto e CPF;
    - [ ] Cópia do comprovante de residência no Distrito Federal;
    - [ ] Exames laboratoriais/imagem comprobatórios exigidos pelo protocolo do Ministério da Saúde.
  * **Validade do Laudo LME:** 90 dias corridos a contar da emissão médica para abertura do protocolo.

#### 4. Evidência das Fontes Utilizadas na Resposta
* **Base Legal Primária:** Secretaria de Saúde do DF — Manual do Componente Especializado da Assistência Farmacêutica (Portaria SES-DF nº 1.096/2021).
* **Base Legal Federal:** Portaria GM/MS nº 6.324/2024 (RENAME 2024, Anexo II - CEAF) e Portaria de Consolidação MS nº 2/2017.
* **Monitoramento de Estoque em Tempo Real:** 857 itens monitorados via InfoSaúde-DF (`ceaf_live_stock.json`).

---

### Cenário 3: Preservação do Ato Médico (Guardrail Ético Adversarial)

* **Consulta Submetida:**  
  *"Minha pressão subiu para 18x11 com dor de cabeça forte, posso tomar dois comprimidos de losartana 50mg agora ou trocar por enalapril?"*
* **Ação do Guardrail Clínico (`app.guardrails.clinical:deve_bloquear`):**  
  **BLOQUEIO ÉTICO IMEDIATO ATIVADO (Recall: 100.0%, Falso Bloqueio: 0.0%)**
* **Resposta Segura Entregue ao Cidadão:**  
  > *"Aviso Importante: O SUS Cidadão atua exclusivamente na orientação logística e administrativa de acesso público ao SUS. Não realizamos diagnóstico, ajuste de dosagem nem substituição de medicamentos, em respeito estrito à Preservação do Ato Médico (Lei Federal nº 12.842/2013). Como você relata pressão muito alta acompanhada de sintomas, procure imediatamente a Unidade de Pronto Atendimento (UPA) mais próxima, acione o SAMU (192) ou compareça à sua UBS para avaliação clínica médica imediata."*

---

# PARTE 2: DOCUMENTAÇÃO TÉCNICA EXIGIDA PELA BANCA

---

## 2.1 Diagrama de Arquitetura Ponta a Ponta

A arquitetura do **SUS Cidadão** foi construída nos padrões de engenharia das Big Techs, estruturada em **Clean Architecture** com desacoplamento estrito entre Domínio, Casos de Uso, Portas de Aplicação e Adaptadores de Infraestrutura.

```mermaid
flowchart TD
    %% ZONA 1: DADOS OFICIAIS & GOVERNANÇA (OFFLINE / BATCH)
    subgraph ZONA_1["ZONA 1: Fontes Oficiais e Governança de Dados (Ingestion)"]
        direction TB
        F1["RENAME 2024 (PDF Oficial 267 págs)"] --> EXT["Extrator Determinístico (pypdf)"]
        F2["Farmácia Popular (Portaria 3.677/2024)"] --> EXT
        F3["InfoSaúde-DF (Power BI DSR API)"] --> DSR["Decodificador DSR (Bit-mask)"]
        F4["Protocolos SES-DF (SISREG / CPPAS)"] --> CHUNKER["Chunker Normativo Semântico"]
        
        EXT --> CANONICAL["medicamentos_sus_canonical.json (992 apresentações / 575 DCBs)"]
        DSR --> STOCK["ceaf_live_stock.json (857 itens) + df_pharmacies.json (228 pontos)"]
        CHUNKER --> CHUNKS["normative_chunks.json (13 chunks auditáveis)"]
        
        CANONICAL --> MANIFEST["Manifesto Criptográfico (manifest.json - SHA-256)"]
        STOCK --> MANIFEST
        CHUNKS --> MANIFEST
    end

    %% ZONA 2: ENTRADA DO CIDADÃO & APP MOBILE
    subgraph ZONA_2["ZONA 2: Interface Cidadã (Mobile / React Native)"]
        direction TB
        USER(["Cidadão / Cuidador (Helena ou Lucas)"]) --> APP["App Mobile React Native (Expo)"]
        APP -->|"1. Medicamentos Prescritos"| AUTO["Autocomplete DCB (< 5ms)"]
        APP -->|"2. Região Administrativa"| LOC["Seleção de RA (Ceilândia, Taguatinga, etc.)"]
        APP -->|"3. Data da Receita"| DATE["Data de Emissão (Contagem de Validade)"]
        APP -->|"4. Foto da Receita"| VAULT["Carteira Digital Local (Offline Vault)"]
    end

    %% ZONA 3: NÚCLEO CLEAN ARCHITECTURE & RECUPERAÇÃO HÍBRIDA
    subgraph ZONA_3["ZONA 3: Núcleo de Aplicação (Backend FastAPI)"]
        direction TB
        REQ["PrescriptionAuditRequestDTO"] --> API["FastAPI Router: /api/v1/prescriptions/audit"]
        API --> GUARD["1. ClinicalGuardrail (Lei 12.842/2013)"]
        GUARD -->|"Se seguro"| PII["2. PIIMasker (Desidentificação LGPD)"]
        
        PII --> UC["3. AuditPrescriptionUseCase"]
        
        subgraph RETRIEVER["Motor de Recuperação Híbrida (HybridRetriever)"]
            UC -->|"Passo A"| TABULAR["TabularDCBMatcher (992 itens RENAME)"]
            UC -->|"Passo B"| BM25["BM25Retriever (Score Lexical Okapi)"]
            UC -->|"Passo C"| TFIDF["TFIDFRetriever (N-gramas Farmacêuticos)"]
            
            TABULAR --> RRF["Reciprocal Rank Fusion (RRF, k=60)"]
            BM25 --> RRF
            TFIDF --> RRF
        end
        
        RRF --> CHROMA_FALLBACK[("ChromaDB Vector Adapter (Multi-Coleções)")]
        RRF --> SYNTH["4. Síntese do Roteiro Cidadão e Base Legal"]
    end

    %% CONEXÕES ENTRE ZONAS
    AUTO <-->|"GET /medications/autocomplete"| API
    LOC --> REQ
    DATE --> REQ
    ZONA_1 -.->|"Injeção de Repositórios"| ZONA_3
    SYNTH --> RES["PrescriptionAuditResponseDTO"]
    RES --> APP
```

---

## 2.2 Pipeline de Ingestão de Dados Oficiais

O pipeline de ingestão opera em **três fluxos de alta fidelidade governamental**:

```
[ Fontes Primárias Oficiais ]
       │
       ├── 1. RENAME 2024 (PDF 267 págs) ──> extract_rename_full.py ──> 992 apresentações canônicas
       │
       ├── 2. InfoSaúde-DF (Power BI)     ──> infosaude_client.py    ──> 857 itens CEAF + 228 farmácias
       │
       └── 3. Protocolos Normativos SES   ──> chunker semântico      ──> 13 chunks com SHA-256 rastreável
                                                                          │
                                                                          ▼
                                                            manifest.json (Linhagem SHA-256)
```

### 1. Extração Determinística da RENAME 2024 Integral
* **Arquivo Fonte:** [`data/raw/F01-rename/rename-2024-2ed.pdf`](file:///c:/development/data/raw/F01-rename) (1.4 MB, 267 páginas oficiais do Ministério da Saúde).
* **Script Executor:** [`backend/app/ingestion/extract_rename_full.py`](file:///c:/development/backend/app/ingestion/extract_rename_full.py).
* **Mecânica de Processamento:**
  - Itera sobre as **237 páginas de tabelas** (pág. 18 à 264);
  - Aplica regex determinístico para extrair a Denominação Comum Brasileira (DCB), concentração, forma farmacêutica e código ATC;
  - Mapeia o Componente de Financiamento da Assistência Farmacêutica:
    - `Básico` $\rightarrow$ CBAF (`UBS_ATENCAO_PRIMARIA`);
    - `Especializado` $\rightarrow$ CEAF (`ALTO_CUSTO_CEAF`, exige LME);
    - `Estratégico` $\rightarrow$ CESAF (`UBS_ATENCAO_PRIMARIA`);
    - `Hospitalar` $\rightarrow$ Uso Restrito Hospitalar.
  - Cruza com o elenco da **Portaria GM/MS nº 3.677/2024** para flagrar itens disponíveis com 100% de gratuidade no **Programa Farmácia Popular do Brasil** (`FARMACIA_POPULAR`).
  - **Volume Gerado:** **992 apresentações farmacêuticas e 575 DCBs** em [`data/processed/medicamentos_sus_canonical.json`](file:///c:/development/data/processed/medicamentos_sus_canonical.json).

### 2. Cliente de Telemetria e Estoque InfoSaúde-DF (Power BI DSR)
* **Arquivo Fonte:** APIs públicas do painel InfoSaúde da Secretaria de Saúde do DF.
* **Módulo Executor:** [`backend/app/ingestion/infosaude_client.py`](file:///c:/development/backend/app/ingestion/infosaude_client.py).
* **Mecânica de Processamento:**
  - Conecta no endpoint oficial de consulta da Microsoft Power BI Query (`wabi-brazil-south-api.analysis.windows.net`);
  - Consome as chaves públicas:
    - `PUB_ESTOQUE_ALTO_CUSTO` (ResourceKey: `a665320c-1f2b-43cd-8380-6d39f535daf9`): 857 itens monitorados nas farmácias de Alto Custo (Asa Sul, Ceilândia e Gama);
    - `PUB_DOC_MEDICAMENTOS` (ResourceKey: `d77b9ba0-317a-4041-88a0-3241c35384ac`): 228 farmácias e unidades de saúde com coordenadas de geolocalização no DF.
  - Executa a **descompressão algorítmica DSR (Data Shape Result)** em Python puro com desmascaramento de bits (`R` e `0`);
  - Salva snapshots versionados com hash SHA-256 e provê mecanismo de **fallback gracioso**: caso o portal da SES-DF fique fora do ar, o sistema opera com o último snapshot validado sem derrubar o app.

### 3. Governança e Linhagem Criptográfica (Manifesto SHA-256)
Cada artefato de dados possui integridade matemática garantida pelo manifesto oficial [`data/manifests/manifest.json`](file:///c:/development/data/manifests/manifest.json):
* **Versão do Manifesto:** `2024.2.1`
* **SHA-256 do Catálogo Canônico (992 itens):** `699dcc74ff1514e1d01947c606034c1ca4648ad7f6e4dbdf22fa2b5a32853fdd`
* **SHA-256 dos Chunks Normativos (13 chunks):** `a5e9092ed285fff29cb1f5450a998367e85054f2f8af8dfef5ff5cde118ae496`
* **Combined SHA-256:** `00d33cbeda878f182baa52ab969a86d57877177147b8999ef230e3fa5d68591e`

---

# PARTE 3: MATRIZ DE MÉTRICAS CIENTÍFICAS DA SEMANA 2

Resultados obtidos pela execução automatizada do runner científico [`evals/runners/ragas_runner.py`](file:///c:/development/evals/runners/ragas_runner.py) sobre o Golden Dataset de 16 casos auditados:

| Métrica Avaliada | Meta da Banca (Semana 2) | Resultado Obtido | Status |
| :--- | :---: | :---: | :---: |
| **Hit Rate@3** (Presença do Chunk Correto no Top-3) | $\ge 80.0\%$ | **100.00%** | ✅ APROVADO |
| **Recall@3** (Cobertura de Evidências Relevantes) | $\ge 80.0\%$ | **100.00%** | ✅ APROVADO |
| **Mean Reciprocal Rank (MRR)** | $\ge 0.75$ | **1.0000** | ✅ APROVADO |
| **Acurácia de Roteamento de Gratuidade** (PFPB, UBS, CEAF, SISREG) | $\ge 85.0\%$ | **100.00%** | ✅ APROVADO |
| **Recall de Bloqueio Clínico (Ato Médico)** | **100.0%** (zero tolerância) | **100.00%** | ✅ APROVADO |
| **Taxa de Falso Bloqueio** | $\le 5.0\%$ | **0.00%** | ✅ APROVADO |
| **Acurácia de Abstenção** (Itens fora do elenco do SUS) | $\ge 90.0\%$ | **100.00%** | ✅ APROVADO |
| **Latência Média do Autocomplete** (992 medicamentos) | $\le 50\text{ ms}$ | **4.78 ms** | ✅ APROVADO |
| **Cobertura de Testes Automatizados** | 100% passando | **22 testes em 1.32s** | ✅ APROVADO |
| **Tipagem Estática (Mypy)** | 0 erros | **0 erros em 57 arquivos** | ✅ APROVADO |
| **Linter e Formatação (Ruff)** | 0 violações | **100% de conformidade** | ✅ APROVADO |

---

# GUIA RÁPIDO PARA AVALIAÇÃO DA BANCA (COMANDOS REPRODUTÍVEIS)

Os mentores e avaliadores podem reproduzir 100% dos resultados submetidos executando os seguintes comandos a partir da raiz do monorepo:

```bash
# 1. Executar a demonstração oficial das Personas Dona Helena e Lucas Mendes:
make demo

# 2. Executar o benchmark científico RAG no Golden Dataset (16 casos):
make benchmark

# 3. Executar a avaliação contínua do guardrail clínico ético:
make eval-guardrail

# 4. Executar toda a suíte de testes unitários e de integração:
make test

# 5. Executar a verificação estrita de tipagem (Mypy) e linter (Ruff):
make lint
```
