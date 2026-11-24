# Portação Controlada — Corpus Consolidado v10 (`data-engineering` → `development`)

Registro formal em conformidade com [portacoes.md](../runbooks/portacoes.md), as [Diretrizes de Integridade Científica e IA](../runbooks/diretrizes_integridade_ia.md) e os [ADRs 0004](../adr/0004_integridade_comparativo_semana3.md) e [0006](../adr/0006_correspondencia_documental_e_evidencias.md).

## 1. Identidade de Origem e Destino

| Campo | Valor verificado |
| --- | --- |
| **Repositório de origem** | `https://github.com/DESAFIO-2/data-engineering.git` |
| **Branch/SHA de origem (`main`)** | `main` @ `8b9f15ac6c1f8a3685ce8ab8a139ffac0857f6cc` |
| **SHA do candidato v10 versionado em Git** | `b63618ea8b855b7a6815c2086a0c3f0eda216936` (`corpus-consolidado-v10-normalizada-2026-11-17`, `release.json` SHA-256 `d99e26e52eca0c3b115c9f7d93fa600b2ca4fe39a885cc268c10ff88252e5921`) |
| **SHA da portação anterior no destino** | `8d76f923354a4707810be38e238a8a3ea035554e` (v9 — `manifest_version: 2026.4.0`) |
| **Base de destino desta portação** | `main` @ `3d0ded556a72fae70f06bfeee8e9cefe60571339` + saneamento Fase 0 (`13a9bb0`) |
| **Branch de destino** | `feat/semana5-multimodalidade` |
| **Manifesto de destino** | `data/manifests/manifest.json` (`manifest_version: 2026.5.0`) e `data/manifests/corpus_v10_source.json` |

## 2. Reprodutibilidade do Release v10 Aprovado

Na origem `main @ 8b9f15a`, os artefatos de releases históricos e derivados foram migrados para DVC (`gdrive://1tPvsMggxEE0UmyrdkqkP9VMoJ9Ow6mZn`). A reprodução determinística a partir do candidato revisado em `b63618e` via `scripts/approve_v10_release.py` em clone temporário isolado produziu:

- **`corpus_fingerprint`:** `b7c41f04be50102ee4550647f8d9109af42c2cd1d07ef9cbeb78d608c240ac92` (idêntico ao publicado em `docs/reports/v10/status-e-checklist-v10.md`).
- **`occurrences.jsonl`:** `2.114` ocorrências (`54d9ac62959797d1a3560201f468694fe56fd2d59863990fc201352811798f34`), 100% preservadas frente à v9, com camada aditiva `normalized` + `54` correções do parser F01 (`53` campos `component` preenchidos e `0/ ,3 mg/mL` → `0,3 mg/mL` em `occ-3c800a169e894016ada0a5c0`).
- **`evidencias.jsonl`:** `2.114` evidências literais com `review_status = "approved"` (`13d1f2ebc2a659c11aa028fecd966c7888db5396fccd8280f934c500d01b30e2`).
- **`chunks.jsonl` (`one-evidence-v3`):** `2.114` textos distintos (`d2f415af483ea6700266f8a255db1880d159e0cc140723dbadc7f87f1cb21570`).
- Aprovação humana registrada em `docs/reports/v10/revisao-v10-normalizada-jhiovana.md` (Jhiovana, `2026-11-18`), estritamente para presença documental F01/F03/F04, normalização aditiva e correções F01 (**não** constitui parecer clínico `H7`).

## 3. Decisão por Artefato

| Artefato da origem | Decisão | Aplicação no destino |
| --- | --- | --- |
| `occurrences.jsonl` e `evidencias.jsonl` v10 | **Adaptar** | Versionados em `data/staging/curated_{occurrences,evidencias}_v10.jsonl` com verificação SHA-256 e schema drift (`OPTIONAL_OCCURRENCE_KEYS` incluindo `normalized`). |
| Receita `CHUNK_RECIPE_V3` (`one-evidence-v3`) | **Adaptar** | Reimplementada em `backend/app/ingestion/consolidate_curated_corpus.py` (`gerar_evidence_chunks_v3`), gerando `data/processed/evidence_chunks_v3.json` com **0 diferenças** nos 2.114 textos frente ao `chunks.jsonl` da origem. |
| Catálogo canônico (`medicamentos_sus_canonical.json`) | **Adaptar (reconciliação por `occurrence_id`)** | Mantidas as `1.708` apresentações reconciliadas por `occurrence_id` e travas do `ADR 0006` (sem sobrescrever com IDs `med-*`). Os `53` componentes F01 preenchidos corrigiram automaticamente **`30` vínculos de rota** (`UBS_ATENCAO_PRIMARIA` → `ALTO_CUSTO_CEAF`, ex.: `somatropina`, `acetato de desmopressina`, `acetato de octreotida`, `acetato de lanreotida`, `calcitonina`, `cloridrato de cinacalcete`, `acetato de fludrocortisona`, `pamoato de pasireotida`). |
| Regras seletivas de `src/rag/consolidated/matching.py` | **Adaptar seletivamente** | Portadas para `backend/app/retrieval/tabular_matcher.py`: unidades `mEq`, `U`, `L` e `%`; sufixo `(liberação de ...)` em `_PACKAGE_SUFFIX_RE` (ex.: rivastigmina 9 mg); suporte a ` ou ` em `pharmaceutical_form` (`form_alternatives`, ex.: `"cápsula ou comprimido"`). |
| `release.json`, `quality_report.json`, `revisao-v10-normalizada-jhiovana.md`, `status-e-checklist-v10.md` | **Referenciar** | Proveniência fixada em `data/manifests/corpus_v10_source.json`. |
| `src/rag/consolidated/*` (chat, CLI, guardrails), `data/vectorstore/chroma/*`, `src/storage/*`, `data/mappings/ubs/*` | **Não importar / Adiar** | Runtime mantém Clean Architecture, LangGraph, guardrails e recuperação lexical determinística sem ChromaDB nem dependência de rede externa. |

## 4. Validação no Consumidor (`development`)

- `python -m app.ingestion.consolidate_curated_corpus`: `1.708` apresentações canônicas (`0` com `occ == 0`), `20` chunks normativos, `2.114` chunks `evidence_chunks_v3.json` (paridade 2.114/2.114 contra origem).
- `PublicContextRegistry`: **0 rejeições** nos 2.114 chunks v3 e nos 20 normativos.
- `ruff`, `mypy --strict`, `pytest` (offline sem rede, com novas regressões v10), `eval-test`, `validar_datasets.py`, `guardrail_runner.py`, Golden Sets v1 (`16/16`) e v2 (`22/22`), `compare-smoke`, `seguranca-smoke` e `smoke_http.py` contra `uvicorn` real.

## 5. Reversão

Para reverter integralmente a portação v10 restaurando o pacote v9 (`manifest_version: 2026.4.0`) e `evidence_chunks_v2.json` sem alterar a Fase 0 ou a Semana 5:
```bash
git revert <SHA_DO_COMMIT_PORTACAO_V10>
```
