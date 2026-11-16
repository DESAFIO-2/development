# Portação Pré-Semana 4 — Corpus Consolidado v9 (`data-engineering` → `development`)

Registro formal em conformidade com o [procedimento de portações](../runbooks/portacoes.md), as [Diretrizes de Integridade Científica e IA](../runbooks/diretrizes_integridade_ia.md) e o [ADR 0004](../adr/0004_integridade_comparativo_semana3.md).

## 1. Identificação de Origem e Destino

| Campo | Valor verificado |
| --- | --- |
| **Repositório de origem** | `https://github.com/DESAFIO-2/data-engineering.git` |
| **SHA de origem fixado** | `8d76f923354a4707810be38e238a8a3ea035554e` |
| **Commit base de destino** | `3fd6d07` (`fix/pre-semana4-seguranca-ci-base`, derivado de `main @ f30644f`) |
| **Branch desta portação** | `feat/pre-semana4-corpus-v9` |
| **Manifesto de destino** | `data/manifests/manifest.json` (`manifest_version: 2026.4.0`) |

## 2. Reprodutibilidade do Release v9 (`pending_review` → `approved`)

No commit `8d76f923354a4707810be38e238a8a3ea035554e` de `data-engineering`:

- O pacote candidato `data/releases/corpus-consolidado-v9-claritromicina-normalizada-2026-11-12` está integralmente versionado no Git com `status: "pending_review"` (`release.json` SHA-256 `60e8218b7968103940894ed513b062f988b085b0e7b01bcdd65a464442f34614`).
- A revisão humana aprovada por Jhiovana (`docs/reports/v9/revisao-claritromicina-v9-jhiovana.md`, SHA-256 `acd85a4445f3220aacfd0e0fd5dea18e901751c25bbcbff181ea6eab452c714a`) e o script determinístico `scripts/approve_v9_release.py` também residem no mesmo commit, ao lado do ponteiro DVC `corpus-consolidado-v9-aprovado-2026-11-12.dvc` (`md5: 2f2b6ad8d089cbfe1e82989697dc647a.dir`, `size: 7148796`, `nfiles: 9`).
- A execução local isolada de `scripts/approve_v9_release.py` reproduziu deterministicamente `corpus-consolidado-v9-aprovado-2026-11-12` (`status: "approved"`, `corpus_fingerprint: 99d4fb04a74463b9cfdd4ea9c08b51a0ef39bb5631be58964209d6041f9e1b20`, `release.json` SHA-256 `a31a695cca85237aa94e52b6fa3211ef140361f0ac9cd47b9985d93f6e0761ae`), preservando 1:1 as `2.114` ocorrências e evidências (`occurrences.jsonl` SHA-256 `d6fb343e6fbeea8cf33fdc91473ddd85231d20c1ad57c801f39a25c2722a3e7f`; `evidencias.jsonl` SHA-256 `95319e1a7ec6d31a2683a64fa62bc0f3960eaddba15c24dcac20560e1484a65f`).

## 3. O que foi Importado, Adaptado, Referenciado e Adiado

### Importado sem alteração
- `data/staging/curated_occurrences_v9.jsonl` (`2.114` ocorrências F01/F03/F04 aprovadas) e `data/staging/curated_evidencias_v9.jsonl` (`2.114` evidências literais), com origem registrada em `data/manifests/corpus_v9_source.json`.
- Correções textuais e de normalização da linha `v6`–`v9`:
  - `occ-ef6f34aca6aebf7145e278f7` (`F01`): hifenização OCR corrigida para `fenoximetilpenicilina potássica`.
  - `occ-bc5acf38f4260802e843100c` (`F03`, **C-F03-003**): `carbonato de cálcio + colecalciferol` corrigido para `"equivalente a 500 ou 600 mg de cálcio + colecalciferol 400 UI"`.
  - `occ-83202f34ce2ffbeed05ea49d` (`F03`, **v9**): `claritromicina` normalizada de `500mg` para `500 mg`, unificando 1 ocorrência `F01` + 3 ocorrências `F03` no mesmo item canônico (`4` ocorrências).
  - Normalização de códigos `F03` (`adalimumabe`, `etanercepte`, `infliximabe`, `rituximabe`), `mikania glomerata spreng`, `dl-metionina` e reordenação de 5 `description_cell` em `F03` (`enoxaparina sódica`, `gonadotropina corionica humana`, `idarrubicina`, `imunoglobulina humana anti-hepatite B`, `simeticona`).
- Receita `CHUNK_RECIPE_V2` (`one-evidence-v2:structured-fields;F03-description-cell;F04-indication;source-provenance;no-old-chunks`).

### Adaptado no consumidor (`development`)
- `backend/app/ingestion/consolidate_curated_corpus.py`:
  - Atualização do contrato de schema drift para `v9` (`validate_occurrence_drift` e `validate_evidencia_drift` validando vínculo 1:1 ocorrência↔evidência, `review_status == "approved"` e ausência de linhas vazias/excluídas).
  - Remoção de separadores de milhar brasileiros em `chave_normalizada_concentracao` (`5.000 UI/0,25 mL` ↔ `5000 UI/0,25 mL`, `1.000 UI` ↔ `1000 UI`, `4.000 UI` ↔ `4000 UI`, `1.000 mg` ↔ `1000 mg`), preservando decimais.
  - Remoção integral dos 5 registros sintéticos `occ == 0` (`MED-ATENOLOL-25MG`, `MED-SALBUTAMOL-100MCG`, `MED-DAPAGLIFLOZINA-10MG` antigo, `MED-SACUBITRIL-VALSARTANA-97-103MG`, `MED-FORMOTEROL-BUDESONIDA-12-400MCG` antigo); todos os `1.776` itens em `data/processed/medicamentos_sus_canonical.json` agora possuem `len(occurrence_ids) >= 1`.
  - Unificação canônica de `dapagliflozina 10 mg` (`F01 + F03 + F04`, `3` ocorrências) mantendo `dispensation_route: "FARMACIA_POPULAR"`, `available_reme_df: true` e orientação explícita em `notes` / `required_documents` para a rota alternativa via CEAF/Alto Custo com LME (`Cód. SES-DF 36801`), e de `sulfato de salbutamol 100 mcg/dose` (`F01 + F03 + F04`, `3` ocorrências).
  - Geração de `data/processed/evidence_chunks_v2.json` (`2.114` chunks únicos `one-evidence-v2`) e remoção dos arquivos obsoletos `data/staging/curated_occurrences_v5.jsonl`, `data/manifests/corpus_v5_source.json`, `data/processed/unified_pdf_chunks.json` e `data/processed/medicamentos_sus_canonical_full.json`.
  - **Nota de escopo Pré-Semana 4:** nenhum repositório/consumidor em `backend/app/` foi criado agora para `evidence_chunks_v2.json` a fim de evitar código morto; a ligação ao pipeline RAG/agentes ocorrerá na Semana 4.
- `backend/app/retrieval/tabular_matcher.py`:
  - Remoção segura de separador de milhar brasileiro preservando decimais (`0,125 mg`, `0,25 mL`).
  - Equivalência escopada de doses em `casar()`: `97 mg + 103 mg` (`97/103 mg`) ↔ `200 mg` (além de `49/51 mg` ↔ `100 mg` e `24/26 mg` ↔ `50 mg`) restrita exclusivamente a `sacubitril valsartana sódica hidratada` (direcionando ao registro real F01+F03 de `200 mg`), e `100 mcg` ↔ `100 mcg/dose` restrita exclusivamente a `sulfato de salbutamol`.
- `observability/mlflow_tracker.py` e `evals/runners/artifacts.py`: alinhamento das tags/hashes ao manifesto `2026.4.0` e `evidence_chunks_v2.json`.

### Referenciado (mantido intacto com pendência registrada)
- `data/processed/normative_chunks.json` (`20` chunks normativos auditados) mantido intacto para preservar integridade dos benchmarks atuais antes da Semana 4.
- **Pendência explícita de curadoria textual para o squad (antes da reavaliação da Semana 4):** revisar e desdobrar `CHK-COMP-PFPB-003` (e ajustar menção análoga em `CHK-PFPB-001`), removendo a referência obsoleta *"Aqui Tem Farmácia Popular"*.

### Adiado (fora do escopo Pré-Semana 4)
- Fontes complementares `C01`–`C17` em Markdown bruto, conectores ao vivo `InfoSaúde Live`, recuperação vetorial (`SPEC-10` / `ChromaDB`), e orquestração multiagente da Semana 4.

## 4. Validação no Consumidor

Checagens executadas na branch `feat/pre-semana4-corpus-v9`:
- `backend/app/ingestion/consolidate_curated_corpus.py`: `1.776` itens canônicos (`0` com `occ == 0`), `20` chunks normativos, `2.114` `evidence_chunks_v2` únicos.
- `evals/runners/ragas_runner.py` (`golden_set_v1.jsonl` e `golden_set_v2_consolidado.jsonl`), `evals/runners/comparar_semana3.py --synthetic-smoke`, `evals/runners/suite_seguranca.py --synthetic-smoke --fail-on-api-elim`, `uv run pytest`, `uv run ruff`, `uv run mypy`, `pip-audit` e `bandit`.

## 5. Reversão

Em caso de regressão após esta portação:
```bash
git checkout fix/pre-semana4-seguranca-ci-base
# ou para reverter um commit específico na branch de portação:
git revert <SHA_DO_COMMIT_PORTACAO_V9>
```
