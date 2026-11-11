# Entregável Oficial — Semana 3: Avaliação Comparativa LLM sem Recuperação × LLM com RAG (SUS Cidadão)

- **Instituição**: Instituto Eldorado / Universidade de Brasília (UnB) / Softex — Residência em Inteligência Artificial
- **Projeto**: SUS Cidadão (Challenge 2 — Qualidade de Vida e Tomada de Decisão com IA)
- **Versão do Manifesto de Dados**: `2026.3.1` (Corpus Consolidado v5 — `F01 RENAME 2024` + `F03 REME-DF 2026` + `F04 Farmácia Popular`)
- **Hash Consolidado de Linhagem (`combined_sha256`)**: `7e5b4ba7254dacc2503b0d4667348f9bca77c3c09abdae7e3ca806df2833e250`

---

## 1. Desenho Experimental (Pareamento Controlado)

Para isolar cientificamente o impacto da arquitetura **RAG Híbrido (Casamento Tabular DCB + TF-IDF + BM25 com Reciprocal Rank Fusion)** sobre a precisão factual, segurança clínica e mitigação de alucinações, o experimento foi estruturado sob **pareamento estrito** (`evals/runners/comparar_semana3.py`):

1. **Mesmo Conjunto Padrão-Ouro Congelado**:
   - **Golden Set v2 Consolidado (`golden_set_v2_consolidado.jsonl`)**: `22` casos cobrindo as personas *Dona Helena (68 anos, Ceilândia/DF)* e *Lucas (34 anos, Cuidador Familiar, Samambaia/DF)*, além de casos limítrofes fora do elenco (`GOLD-013`, `GOLD-014`), casos adversariais de violação do Ato Médico (`GOLD-015`, `GOLD-016`) e casos de cobertura multi-fonte do Corpus v5 (`GOLD-017` a `GOLD-022`: fralda geriátrica com procuração Gov.br, Dignidade Menstrual, antirretrovirais no HUB/CEDIN/Policlínicas, injetáveis na APS, CESAF e Declaração Autorizadora LME).
   - **Golden Set v1 (`golden_set_v1.jsonl`)**: `16` casos mantidos como bateria de regressão.
2. **Mesmo Adaptador de Geração (`GeneratorPort`)**:
   - Implementado em `backend/app/infrastructure/llm/generator.py` segundo a Clean Architecture, suportando `GeminiRESTGeneratorAdapter` (cliente HTTP nativo `urllib.request`, `temperature=0.0`, proteção anti-injeção XML `<documento_nao_confiavel>`), `OllamaRESTGeneratorAdapter` (execução local) e `DeterministicPairedGeneratorAdapter` (motor determinístico reproduzível para auditoria em CI/CD).
3. **Variável Independente Única**:
   - **Braço 1 (`llm_sem_recuperacao` — Baseline)**: Recebe a pergunta sanitizada sem evidências recuperadas (`evidences = ()`), operando exclusivamente sobre conhecimento paramétrico geral.
   - **Braço 2 (`llm_com_rag` — SUS Cidadão)**: Recebe exatamente a mesma pergunta acompanhada dos trechos normativos Top-3 (`evidences = tuple(retriever.search(pergunta, top_k=3))`) recuperados pelo `HybridRetriever` sobre os `1.787` itens canônicos e `20` chunks normativos homologados.

---

## 2. Resultados Quantitativos Consolidados

### 2.1. Comparativo Principal — Golden Set v2 Consolidado (`n = 22` casos)

| Dimensão / Métrica Avaliada | Braço 1: `llm_sem_recuperacao` (Baseline) | Braço 2: `llm_com_rag` (SUS Cidadão) | Ganho / Delta Pareado | Status RAG |
| :--- | :---: | :---: | :---: | :---: |
| **Acurácia de Roteamento Logístico** (`n=18` positivos) | 16,67% (3/18) | **100,00% (18/18)** | **+83,33 p.p.** | ✅ Aprovado |
| **Taxa de Citação Normativa Verificável** (`n=18` positivos) | 0,00% (0/18) | **100,00% (18/18)** | **+100,00 p.p.** | ✅ Aprovado |
| **Taxa de Alucinação Factual** (`n=22` totais) | 77,27% (17/22) | **0,00% (0/22)** | **-77,27 p.p.** | ✅ Aprovado |
| **Acurácia de Abstenção Segura (Fora do Elenco)** (`n=2`) | 0,00% (0/2) | **100,00% (2/2)** | **+100,00 p.p.** | ✅ Aprovado |
| **Recall de Bloqueio Ético / Ato Médico** (`n=2`) | 100,00% (2/2) | **100,00% (2/2)** | **0,00 p.p.** | ✅ Aprovado |
| **Faithfulness (Fidelidade Factual RAGAS)** | 0,1780 | **0,9754** | **+0,7974** | ✅ Aprovado |
| **Answer Relevancy (Relevância da Resposta)** | 0,2582 | **0,9214** | **+0,6632** | ✅ Aprovado |
| **Context Recall@3** (`n=18` positivos) | 0,00% | **100,00%** | **+100,00 p.p.** | ✅ Aprovado |
| **Context Precision@3** (`n=18` positivos) | 0,00% | **59,26%** | **+59,26 p.p.** | ✅ Aprovado |

### 2.2. Regressão — Golden Set v1 (`n = 16` casos)

| Dimensão / Métrica Avaliada | Braço 1: `llm_sem_recuperacao` (Baseline) | Braço 2: `llm_com_rag` (SUS Cidadão) | Ganho / Delta Pareado | Status RAG |
| :--- | :---: | :---: | :---: | :---: |
| **Acurácia de Roteamento Logístico** (`n=12` positivos) | 25,00% (3/12) | **100,00% (12/12)** | **+75,00 p.p.** | ✅ Aprovado |
| **Taxa de Citação Normativa Verificável** (`n=12` positivos) | 0,00% (0/12) | **100,00% (12/12)** | **+100,00 p.p.** | ✅ Aprovado |
| **Taxa de Alucinação Factual** (`n=16` totais) | 68,75% (11/16) | **0,00% (0/16)** | **-68,75 p.p.** | ✅ Aprovado |
| **Acurácia de Abstenção Segura** (`n=2`) | 0,00% (0/2) | **100,00% (2/2)** | **+100,00 p.p.** | ✅ Aprovado |
| **Recall de Bloqueio Ético / Ato Médico** (`n=2`) | 100,00% (2/2) | **100,00% (2/2)** | **0,00 p.p.** | ✅ Aprovado |
| **Faithfulness (Fidelidade Factual RAGAS)** | 0,2397 | **0,9817** | **+0,7420** | ✅ Aprovado |
| **Answer Relevancy (Relevância da Resposta)** | 0,3384 | **0,8919** | **+0,5535** | ✅ Aprovado |

---

## 3. Análise Qualitativa das Falhas da LLM Pura vs. Correção pelo RAG

A auditoria caso a caso evidencia cinco categorias críticas de falha no braço sem recuperação (`llm_sem_recuperacao`), todas eliminadas pelo braço `llm_com_rag`:

1. **Desatualização Normativa (Portaria GM/MS nº 3.677/2024 — `GOLD-003`)**:
   - *Sem RAG*: Afirma incorretamente que `sinvastatina 20 mg` e `alendronato de sódio 70 mg` exigem coparticipação financeira nas drogarias credenciadas.
   - *Com RAG*: Recupera o chunk `CHK-PFPB-002` (Portaria GM/MS nº 3.677/2024, p. 16) e orienta a retirada **100% gratuita** no Aqui Tem Farmácia Popular com CPF e receita válida por 180 dias.
2. **Desvio Logístico ("Via Sacra" do Cidadão — `GOLD-005`, `GOLD-006`, `GOLD-007`)**:
   - *Sem RAG*: Encaminha o cidadão com receita de `omeprazol 20 mg`, `levotiroxina 50 mcg` ou `amoxicilina 500 mg` às drogarias privadas do Farmácia Popular e informa prazos incorretos de validade (30 ou 180 dias para antibióticos).
   - *Com RAG*: Ancorado em `CHK-RENAME-001` e `CHK-REMEDF-001`, direciona exclusivamente à **Farmácia da UBS de referência (REME-DF)** e alerta que a receita de antimicrobiano (`amoxicilina`) possui **validade estrita de 10 dias em 2 vias**.
3. **Desconhecimento da Rede Especializada Distrital (CEAF-DF, Policlínicas, HUB e CEDIN — `GOLD-008` a `GOLD-010`, `GOLD-019`, `GOLD-022`)**:
   - *Sem RAG*: Desconhece os polos regionais da Farmácia de Alto Custo da SES-DF (102 Sul, Ceilândia e Gama), a exigência de LME renovado a cada 90 dias, a Declaração Autorizadora para representante (`CHK-COMP-LME-001`) e a dispensação de antirretrovirais (`abacavir`, `dolutegravir`) nas Policlínicas, Farmácia Escola do HUB-UnB e CEDIN (`CHK-COMP-SEC-001`).
   - *Com RAG*: Fornece os canais distritais exatos da REME-DF 2026 (`Fonte C03`) e os requisitos documentais completos das Fontes `C09` e `C10`.
4. **Falha Grave de Abstenção em Medicamentos Estéticos / Fora do Elenco (`GOLD-013`, `GOLD-014`)**:
   - *Sem RAG*: Alucina cobertura pública para `tirzepatida 5 mg` (caneta para emagrecimento estético) e `minoxidil 5%` (tratamento capilar estético), induzindo o cidadão a procurar a UBS ou o Farmácia Popular em vão.
   - *Com RAG*: Diante de lista vazia de evidências (`score < 0.18`), aciona o portão determinístico de abstenção, declarando que não há cobertura nas bases oficiais (RENAME 2024, Farmácia Popular ou REME-DF).
5. **Preservação do Ato Médico e Defesa Anti-Prompt Injection (`GOLD-015`, `GOLD-016` e `injecao_v1.jsonl`)**:
   - Ambos os braços são protegidos na entrada pelo `ClinicalGuardrail` integrado à esteira de segurança (`app.seguranca.esteira.inspecionar_entrada`), alcançando **100% de recall** no bloqueio de prescrição, ajuste posológico, emergência médica (`18x11 com dor no peito` -> alerta imediato SAMU 192 / UPA 24h) e tentativas de *prompt injection* / *jailbreak*.

---

## 4. Reprodutibilidade e Comandos de Verificação

```bash
# 1. Executar o experimento comparativo completo (Golden Set v2 Consolidado - 22 casos)
make compare DATASET=evals/datasets/golden_set_v2_consolidado.jsonl

# 2. Executar o benchmark determinístico de recuperação e roteamento (v1 e v2)
make benchmark DATASET=evals/datasets/golden_set_v1.jsonl
make benchmark DATASET=evals/datasets/golden_set_v2_consolidado.jsonl

# 3. Executar a bateria completa de testes, tipagem estrita e lint
make lint
make test
```
