# SPEC-DEV-002: Portagem do Corpus Consolidado, Reconciliação de Chunks e Rastreabilidade MLflow

- **Status:** Implementado e Auditado
- **Fase:** Semana 3 (Consolidação Multi-Fonte RENAME + REME-DF + PFPB, Reconciliação de Chunks e Rastreabilidade Experimental MLflow)
- **Data:** 10/11/2026
- **Responsáveis:** Esquadrão SUS Cidadão (Samuel, Mickeias, Marlon, Jhiovana, Tayrine)
- **Filosofia de Engenharia:** *Ponytail Architecture* (KISS, YAGNI, Zero Asset Bloat, Clean Architecture, Spec-Driven Development)

---

## 1. Contexto & Diagnóstico Técnico

Na evolução entre a Semana 2 e a Semana 3 do **Challenge 2 — SUS Cidadão (NavegaSUS)**, a frente de Engenharia de Dados (`DESAFIO-2/engenharia-dados`) realizou um trabalho fundamental de curadoria humana sobre três fontes normativas oficiais:
- **F01 (`RENAME 2024`, 2ª Edição):** 996 ocorrências em `occurrences.jsonl`;
- **F03 (`REME-DF 2026-10-29`):** 1.078 ocorrências (1.077 válidas após expurgo da linha 987 em branco do PDF original), incluindo códigos SES-DF (`MSE`/`MB`) e canais exatos de dispensação no Distrito Federal (Farmácia do Componente Especializado, UBS Ambulatorial, UBS de Referência para Controle Especial Portaria 344/98, Policlínicas, Farmácia Escola HUB-UnB, CEDIN, HBDF e Uso Hospitalar);
- **F04 (`Elenco Farmácia Popular 2026`):** 41 itens (39 medicamentos e 2 insumos: fralda geriátrica e absorvente higiênico);
- **Fontes Complementares (`C01` a `C17`):** Normas administrativas de dispensação na SES-DF, regras de procuração, dignidade menstrual, atenção secundária (Policlínicas/CAPS/HUB-UnB), abrangência regional do CEAF-DF e painéis InfoSaúde.

### 1.1 Diagnóstico de Dessincronização dos Chunks (Problema Crítico Resolvido)

A auditoria rigorosa dos artefatos de origem revelou dois problemas estruturais nos chunks legados:
1. **No repositório `engenharia-dados` (`scripts/consolidate_corpus.py`):** O script aplicou **283 correções humanas auditadas** (`review-log.jsonl`) sobre `occurrences.jsonl` e `catalog.jsonl` (`review_status = "approved"`), corrigindo princípios ativos truncados, concentrações e formas farmacêuticas. Contudo, na linha 1097 de `consolidate_corpus.py`, o arquivo `chunks.jsonl` foi apenas copiado em bytes brutos da pasta experimental antiga (`"chunks.jsonl": (exp_dir / "chunks.jsonl").read_bytes()`). Como consequência:
   - **2.113 de 2.115** chunks de linhas tinham `medicine_id` obsoleto que não batia com `catalog.jsonl`;
   - **2.620 de 2.620** chunks permaneciam com `review_status = "pending"`;
   - **222 ocorrências da REME-DF (F03)** e **todas as 41 ocorrências do Farmácia Popular (F04)** estavam com `medicine_id = null` nos chunks.
2. **No repositório `development` (`data/processed/unified_pdf_chunks.json`):** Os chunks da categoria `catalogo_canonico_sus` (`CATALOGO_CANONICO_MEDICAMENTOS_SUS_p001_c00` a `c03`) ainda refletiam a base antiga não consolidada (*"Total de Apresentações Padronizadas: 24 medicamentos prioritários auditados"*) e apresentavam quebras lexicais no meio de palavras (`"UBS_ATENCAO_PRIMARI A"`, `"lol 25 mg"`).

---

## 2. Solução Arquitetural (Clean Architecture + Ponytail)

Em vez de copiar scripts procedurais ou acoplar CLIs experimentais ao domínio, a portagem é realizada por um pipeline determinístico, estritamente tipado (`mypy --strict`) e aderente à **Clean Architecture**:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     Ingestion & Curation Layer                           │
│   backend/app/ingestion/consolidate_curated_corpus.py                    │
│   - Validação de Schema Drift (validate_occurrence_drift)                │
│   - Normalização de espaçamento de concentração (50mg -> 50 mg)          │
│   - Fusão Multi-Fonte Determinística (F01 RENAME + F03 REME-DF + F04)    │
│   - Regeneração 100% Consolidada de Chunks Normativos e PDF Chunks       │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ Materializa JSON + SHA-256 Lineage
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                 Data & Persistence Layer (Gold Artifacts)                │
│   - data/processed/medicamentos_sus_canonical.json (1.600+ itens)        │
│   - data/processed/normative_chunks.json (20 chunks curados F01..C14)    │
│   - data/processed/unified_pdf_chunks.json (100% consolidado, approved)  │
│   - data/manifests/manifest.json (v2026.3.0 com hashes SHA-256)          │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ Consome via Ports & Repositories
                                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│           Retrieval, Use Cases & MLflow Observability Layer              │
│   - TabularDCBMatcher + HybridRetriever (RRF)                            │
│   - AuditPrescriptionUseCase (Guardrail Clínico + Roteamento SUS-DF)     │
│   - observability/mlflow_tracker.py + evals/runners/ragas_runner.py      │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Regras de Unificação e Roteamento Multi-Fonte (`F01 + F03 + F04`)

1. **Normalização Canônica de Chave (`dcb_norm`, `conc_norm`, `form_norm`):**
   - Espaçamento padronizado entre valor numérico e unidade (`50mg` $\rightarrow$ `50 mg`, `100mcg` $\rightarrow$ `100 mcg`, `100ui/ml` $\rightarrow$ `100 UI/mL`), permitindo que apresentações idênticas da RENAME (`F01`), REME-DF (`F03`) e Farmácia Popular (`F04`) sejam fundidas no mesmo registro canônico.
   - Remoção de marcadores de rodapé residuais (`dapsona*` $\rightarrow$ `dapsona`, `50 mg*` $\rightarrow$ `50 mg`) e expurgo de linhas em branco (`[linha 987 em branco no PDF]`).
2. **Hierarquia Determinística de Rota de Dispensação (`dispensation_route`):**
   - **`FARMACIA_POPULAR`**: Presente em `F04` ou no elenco oficial de gratuidade plena do PFPB (`available_pfpb = True`, `pfpb_free = True`, validade `180 dias`, ou `365 dias` para contraceptivos);
   - **`ALTO_CUSTO_CEAF`**: Componente `Especializado` na RENAME (`F01`) ou canal `Farmácia do Componente Especializado` na REME-DF (`F03`) (`requires_lme = True`, validade `90 dias`);
   - **`HOSPITALAR`**: Uso exclusivamente hospitalar, pré-hospitalar (SAMU) ou hemocentro/oncologia hospitalar sem dispensação ambulatorial em UBS (`prescription_validity_days = 30`);
   - **`UBS_ATENCAO_PRIMARIA`**: Medicamentos do Componente Básico/Estratégico e da rede ambulatorial SES-DF (UBS, UBS de Referência para Controle Especial Portaria 344/98 com validade `30 dias`, Antimicrobianos RDC 20/2011 com validade `10 dias`, Policlínicas, Farmácia Escola HUB-UnB e CEDIN), enriquecidos no campo `notes` com o código SES-DF (`source_code`) e o canal exato da REME-DF (`F03`).

### 2.2 Reconciliação Integral dos Chunks

1. **`data/processed/normative_chunks.json`:**
   - Preserva integralmente os 13 chunks fundamentais da Semana 2 (`CHK-PFPB-001..002`, `CHK-RENAME-001..002`, `CHK-REMEDF-001..002`, `CHK-SISREG-001..002`, `CHK-VALIDADE-001`, `CHK-REGRA-*`), garantindo **regressão zero** no `golden_set_v1.jsonl`;
   - Adiciona **7 novos chunks normativos curados** a partir das fontes oficiais `C01`, `C02`, `C03`, `C04`, `C06/C07`, `C09/C10` e `C14` (cobrindo Dignidade Menstrual/Fraldas Geriátricas, Atenção Secundária/Policlínicas/CAPS/HUB-UnB, Regionalização das 3 Farmácias de Alto Custo do DF por Região Administrativa, Painel InfoSaúde DF e Componente Estratégico CESAF).
2. **`data/processed/unified_pdf_chunks.json`:**
   - Substitui os chunks defasados de 24 medicamentos pelos chunks gerados diretamente a partir da base consolidada (`F01 + F03 + F04`), garantindo que todos os chunks tenham `review_status: "approved"`, `sha256` verificável e zero palavras truncadas.

### 2.3 Rastreabilidade Experimental com MLflow (`observability/mlflow_tracker.py`)

- Implementa o adaptador `MLflowExperimentTracker` seguindo o princípio *Ponytail* (zero dependência pesada obrigatória no runtime, suporte nativo ao pacote `mlflow` quando instalado via `importlib` e persistência determinística de artefatos de execução em `evals/reports/mlflow_runs/`).
- Registra em cada execução do `ragas_runner.py`:
  - **Parâmetros (`params`):** `retriever_type`, `rrf_k`, `min_score`, `top_k`, `dataset_name`, `canonical_medications_count`, `normative_chunks_count`;
  - **Linhagem de Dados (`tags`):** `manifest_version`, `canonical_medications_sha256`, `normative_chunks_sha256`, `combined_sha256`;
  - **Métricas (`metrics`):** `hit_rate_at_3`, `recall_at_3`, `mrr`, `acuracia_roteamento`, `taxa_bloqueio_clinico`, `acuracia_abstencao`.

---

## 3. Critérios de Aceitação (Quality Gates)

1. **Integridade do Corpus Consolidado:** `medicamentos_sus_canonical.json` deve conter $> 1.600$ apresentações únicas consolidadas entre `F01`, `F03` e `F04`, sem linhas em branco ou asteriscos residuais.
2. **Sincronia de Chunks:** Nenhum chunk em `normative_chunks.json` ou `unified_pdf_chunks.json` pode conter referências ao antigo limite de "24 medicamentos prioritários" ou status `"pending"`.
3. **Zero Regressão Científica:** `ragas_runner.py` deve atingir `Hit@3 = 100%`, `Recall@3 = 100%`, `MRR = 1.0000`, `Acurácia de Roteamento = 100%`, `Bloqueio Clínico = 100%` e `Abstenção = 100%` tanto no `golden_set_v1.jsonl` quanto no novo `golden_set_v2_consolidado.jsonl`.
4. **Qualidade de Código Enterprise:** Aprovação integral em `ruff format --check`, `ruff check`, `mypy --strict` e `pytest`.
