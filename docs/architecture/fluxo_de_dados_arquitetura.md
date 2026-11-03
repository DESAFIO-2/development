# 🏥 Fluxo de Dados e Arquitetura do Sistema — SUS Cidadão (NavegaSUS)

> **Challenge 2: Qualidade de Vida e Tomada de Decisão com IA**  
> *Instituto Eldorado / UnB / Softex / MCTI*

---

## 1. Visão Geral da Arquitetura (Enterprise Dataflow)

Este documento detalha o fluxo de dados ponta a ponta do projeto **SUS Cidadão**, estruturado no padrão empresarial adotado por Big Techs e healthtechs de missão crítica. 

O sistema é dividido em **4 Zonas Arquiteturais**:
1. **Zona 1 (Governança e Ingestão de Dados Oficiais):** Pipeline offline/batch que normaliza as regras governamentais na Denominação Comum Brasileira (DCB) e alimenta o banco vetorial;
2. **Zona 2 (Ingestão Multimodal e Privacidade LGPD):** Captura pelo app mobile React Native e sanitização de dados sensíveis em memória volátil;
3. **Zona 3 (Núcleo de Decisão e Recuperação Híbrida):** Orquestração dos casos de uso, consulta determinística tabular e busca semântica em portarias;
4. **Zona 4 (Entrega Cidadã e LLMOps):** Exibição do roteiro de retirada gratuita e rastreamento contínuo de latência, fidelidade factual (RAGAS) e custos.

---

## 2. Diagrama de Fluxo de Dados Ponta a Ponta

```mermaid
flowchart TD
    %% ZONA 1: DADOS OFICIAIS & GOVERNANÇA (OFFLINE / BATCH)
    subgraph ZONA_1["ZONA 1: Fontes Oficiais e Governança de Dados"]
        direction TB
        F1["RENAME 2024 (Portaria GM/MS 6.324)"] --> ETL["ETL & Normalização DCB (Ingestion Engine)"]
        F2["Farmácia Popular (Elenco Gratuito MS)"] --> ETL
        F3["REME-DF (Relação SES-DF)"] --> ETL
        F4["Protocolos SISREG / CPPAS (DF)"] --> ETL
        
        ETL --> MAN["Data Manifests (YAML: hashes, datas e versões)"]
        ETL --> TAB["Tabela Canônica Estruturada (Parquet / SQLite)"]
        ETL --> CHK["Chunks Normativos e Regras de Laudo LME"]
        
        CHK --> EMB_OFF["Modelo de Embeddings (BAAI/bge-m3)"]
        EMB_OFF --> VEC[("Vector Store (ChromaDB)")]
    end

    %% ZONA 2: INGESTÃO MULTIMODAL & PRIVACIDADE (MOBILE & REAL-TIME)
    subgraph ZONA_2["ZONA 2: Ingestão do Cidadão e Privacidade LGPD"]
        direction TB
        USER(["Cidadão / Cuidador (Helena ou Lucas)"]) --> APP["App Mobile (React Native / Expo)"]
        
        APP -->|"1. PDF Digital (CFM)"| PARSE_PDF["Parser Digital (pdfplumber)"]
        APP -->|"2. Foto de Receita Física"| OCR_VLM["Visão Multimodal (VLM / Gemini Flash)"]
        APP -->|"3. Áudio da Região Adm."| ASR["Transcrição de Voz (Whisper)"]
        
        PARSE_PDF --> RAW_TEXT["Texto Bruto da Prescrição"]
        OCR_VLM --> RAW_TEXT
        ASR --> RAW_TEXT
        
        RAW_TEXT --> PII["PII Masking (LGPD: Regex/NER - CPF, Cartão SUS, Nome)"]
        PII --> HITL{"Human-in-the-Loop: Usuário confirma remédios na tela?"}
        HITL -->|"Não (Editar)"| APP
        HITL -->|"Sim (Confirmado)"| REQ["PrescriptionPayload (JSON Estruturado)"]
    end

    %% ZONA 3: NÚCLEO DE DECISÃO & RAG HÍBRIDO (BACKEND FASTAPI)
    subgraph ZONA_3["ZONA 3: Núcleo de Aplicação e RAG Híbrido (Clean Architecture)"]
        direction TB
        REQ --> API["FastAPI Router: /api/v1/prescriptions/audit"]
        API --> UC["UseCase: AuditPrescriptionUseCase"]
        
        UC --> GUARD_IN{"Guardrail Clínico: Pedido de diagnóstico ou troca de remédio?"}
        GUARD_IN -->|"Sim (Bloqueio)"| BLOCK["Alerta: Preservação do Ato Médico (Retornar ao Prescritor)"]
        
        GUARD_IN -->|"Não (Válido)"| HYBRID["Hybrid Retriever (Orquestrador de Busca)"]
        
        %% Ramo Determinístico
        HYBRID -->|"Busca Exata por DCB + Concentração"| TAB
        TAB -->|"Match: Cobertura PFPB ou UBS"| DET_RESULT["Resultado Determinístico (CBAF / Farmácia Popular)"]
        
        %% Ramo Semântico
        HYBRID -->|"Busca Vetorial: Critérios LME / SISREG"| EMB_ON["Embeddings da Consulta"]
        EMB_ON --> VEC
        VEC -->|"Top-K Chunks Relevantes"| RERANK["Reranker (Cross-Encoder BGE)"]
        RERANK --> SEM_RESULT["Contexto Normativo Auditado"]
        
        DET_RESULT --> SYNTH["Prompt de Síntese Cidadã"]
        SEM_RESULT --> SYNTH
        
        SYNTH --> LLM["LLM Synthesizer (Zero Prescrição / Ancoragem Estrita)"]
        LLM --> GUARD_OUT{"Guardrail de Saída: Citação de portaria e sem alucinação?"}
        GUARD_OUT -->|"Aprovado"| GUIDANCE["CitizenGuidanceCard (Pydantic Schema)"]
    end

    %% ZONA 4: ENTREGA & OBSERVABILIDADE (MONITORAMENTO)
    subgraph ZONA_4["ZONA 4: Experiência Cidadã e LLMOps"]
        direction TB
        GUIDANCE --> RESP_APP["App Mobile: Roteiro Visual Descomplicado"]
        
        RESP_APP --> CARD1["Onde Ir: Farmácia Popular, UBS ou Alto Custo"]
        RESP_APP --> CARD2["O que Levar: Checklist Documental (RG, CPF, LME)"]
        RESP_APP --> CARD3["Gestão da Receita: Alertas a 15 e 7 dias do vencimento"]
        
        BLOCK --> RESP_APP
        
        %% Telemetria
        UC -.->|"Traces & Latência"| OTEL["OpenTelemetry / Langfuse"]
        GUIDANCE -.->|"Avaliação Offline"| RAGAS["Framework RAGAS (Faithfulness >= 0.92)"]
    end
```

---

## 3. Detalhamento das Etapas do Fluxo

### Passo 1: Ingestão de Dados e Linhagem (Zona 1)
- **Origem dos Dados:** RENAME 2024 (Portaria GM/MS nº 6.324/2024), Elenco da Farmácia Popular (atualizado em 2026), REME-DF (SES-DF) e Protocolos SISREG/CPPAS.
- **Data Lineage:** Cada documento gera um manifesto YAML em `data/manifests/` contendo data de publicação, hash do arquivo e órgão emissor.
- **Bifurcação de Armazenamento:**
  - *Tabela Canônica (Parquet/SQLite):* Armazena `dcb_principio_ativo`, `concentracao`, `forma_farmaceutica` e flags de gratuidade (PFPB e REME-DF).
  - *Vector Store (ChromaDB):* Armazena chunks semânticos com regras de laudos LME e critérios de agendamento de exames.

### Passo 2: Entrada do Usuário e Anonimização LGPD (Zona 2)
- O cidadão envia a prescrição pelo app **React Native**.
- **PII Masking:** Antes de qualquer processamento por modelos de IA, um pipeline baseado em Regex e NER substitui Nome, CPF e Cartão SUS por tokens anônimos (`[PACIENTE_ANONIMIZADO]`, `[CPF_MASCARADO]`).
- **Human-in-the-Loop (HITL):** A lista de medicamentos identificada é exibida na tela do celular para confirmação do usuário antes de disparar a auditoria no SUS.

### Passo 3: Núcleo de Decisão e RAG Híbrido (Zona 3)
- O backend **FastAPI** recebe a requisição no endpoint `/api/v1/prescriptions/audit` e aciona o caso de uso `AuditPrescriptionUseCase`.
- **Guardrail de Segurança Clínica:** Se a consulta contiver perguntas de automedicação ("posso dobrar a dose?", "qual remédio substitui este?"), o sistema bloqueia imediatamente e orienta o retorno ao médico.
- **Recuperação Híbrida (Hybrid Retrieval):**
  1. *Ramo Determinístico:* Faz match exato por princípio ativo (DCB) na tabela canônica. Se o remédio é Losartana 50mg, o sistema determina imediatamente: *Disponível 100% gratuito na Farmácia Popular (drogaria privada com CPF) e na UBS*.
  2. *Ramo Semântico:* Para remédios que exigem processo de Alto Custo (ex.: Dapagliflozina 10mg) ou exames (Ecocardiograma), busca nos chunks vetoriais os critérios clínicos e documentos exigidos.
- **Síntese Cidadã:** A LLM atua exclusivamente como redatora empática e acessível, traduzindo termos técnicos sem criar novas regras.

### Passo 4: Entrega ao Cidadão e Observabilidade (Zona 4)
- O app exibe o **Roteiro Cidadão**:
  - **Onde ir:** Mapa da drogaria credenciada mais próxima ou UBS;
  - **O que levar:** Documento com foto, CPF, receita válida e formulário LME preenchido (se aplicável);
  - **Validade da receita:** Contagem regressiva com notificações push locais a 15 e 7 dias do vencimento.
- **LLMOps e Telemetria:** Toda requisição gera traces de latência e consumo de tokens via OpenTelemetry, e as respostas são avaliadas periodicamente contra o *Golden Dataset* com o framework **RAGAS** (meta de *Faithfulness* $\ge 0,92$).
