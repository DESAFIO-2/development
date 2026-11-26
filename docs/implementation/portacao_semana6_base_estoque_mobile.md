# Portação Controlada — Base Mobile & Fluxo de Estoque CEAF / Farmácias (Semana 6)

Registro formal conforme [portacoes.md](../runbooks/portacoes.md), mantendo separação entre código de produto (`development`), experimentos (`Data-Science`) e UI inicial (`Front-End-`).

## 1. Identidade de Origem e Destino

| Campo | Valor verificado |
| :--- | :--- |
| **Branch/SHA de destino (`development`)** | `feat/semana6-base-integracao` (baseada em `fix/semana4-calibracao-e-revisao @ 4197613`, sobre `origin/main @ 44f4911`) |
| **Origem A — Estoque & APIs Mobile** | `https://github.com/DESAFIO-2/Data-Science.git`, branch `main` @ `677cd37` (protótipo mobile integrado em `c3b533a`) |
| **Origem B — Base Visual Expo / NativeWind** | `https://github.com/DESAFIO-2/Front-End-.git`, branch `main` @ `57c861e` |
| **Origem C — Referência de Contratos InfoSaúde & UBS** | `https://github.com/DESAFIO-2/data-engineering.git`, branch `main` @ `8b9f15a` (`SPEC-05`, `SPEC-06`, pendência `H6`) |

## 2. Decisões por Artefato

| Artefato de Origem | Decisão | Aplicação no Destino |
| :--- | :--- | :--- |
| `Front-End- @ 57c861e` (telas, layout, tokens, notificações locais/pulseira) | **Importar (base inicial)** | Copiado para `mobile/` (excluindo `.git`, `node_modules`, `.expo`), sem reescrever telas de exemplo para preservar entrega limpa ao especialista de Front-End. |
| `Data-Science/prototype/src/services/api.ts` (`c3b533a`) | **Adaptar** | Reescrito em `mobile/src/services/api.ts` removendo rotas proprietárias inexistentes no produto (`/v1/chat`, `/v1/voice-turn`, `/v1/tts`, `/v1/sessions/{id}`) e espelhando estritamente `backend/app/api/` (`/health`, `/api/v1/medications/autocomplete`, `/api/v1/prescriptions/audit`, `/api/v1/agents/orchestrate`, `/api/v1/agents/multimodal`, `/api/v1/pharmacies/nearby`, `/api/v1/ceaf-stock`). |
| `Data-Science/data/gold/{ceaf_live_stock,df_pharmacies_geolocated}.json` (`677cd37`) | **Importar** | `ceaf_live_stock.json` importado em `data/processed/` (`857` registros CEAF coletados em `2026-11-25T19:05:59.878064+00:00`, preservado em `synced_at_utc`, com `panel_updated_at_utc=2026-11-25T17:51:59+00:00` extraído da última atualização da fonte em `25/11/2026 14:51:59` BRT); `df_pharmacies_geolocated.json` verificado idêntico (`231` estabelecimentos / `174` geolocalizados). |
| `Data-Science/src/sus_cidadao_ds/ingestion/infosaude_client.py` + `.github/workflows/infosaude-stock-sync.yml` | **Adaptar** | Reimplementado sem dependências externas em `backend/app/ingestion/infosaude_sync.py` (apenas stdlib `urllib.request` com trava HTTPS, decoder DSR e separação entre `panel_updated_at_utc` da fonte e `synced_at_utc` da coleta), executável da raiz com `PYTHONPATH=backend uv run --project backend python -m app.ingestion.infosaude_sync --output-dir data/processed`, e workflow `.github/workflows/infosaude-stock-sync.yml` abrindo PR em `chore/infosaude-stock-sync` (respeitando proteção de `main`). Em produção, os snapshots são copiados para a imagem Docker e carregados em memória por processo: novos snapshots entram no ar após merge do PR e rebuild/redeploy da imagem. |
| `Data-Science/src/sus_cidadao_ds/agents/ports.py` (`PharmacyRepositoryPort.find_nearby`) + rotas `/v1/pharmacies/nearby`, `/v1/ceaf-stock` | **Adaptar (Clean Architecture)** | Contratos em `backend/app/application/pharmacy_stock.py`, repositório `LocalPharmacyStockRepository` reusando `normalizar_texto_pt`, filtro estrito por `ra`/`q` (CEAF não vaza para buscas de outra RA), ordenação estrita por menor `distance_km` quando há coordenadas GPS (`lat`/`lng`), cálculo de `updated_at` e `stale_warning` por item, com resumo conservador de todos os resultados filtrados (ADR 0009), sem usar a data máxima do painel como garantia de frescor, sanitização LGPD (`GuardrailPort.desidentificar_dados_pessoais`) nos parâmetros ecoados (`ra`, `query`, `unidade`), explicitação de `cobertura_ubs_disponivel=false`, e rotas `/api/v1/pharmacies/nearby` e `/api/v1/ceaf-stock` com validação OpenAPI (`math.isfinite`). |
| `Data-Science` ChromaDB, `/v1/tts`, `/v1/sessions` (memória SQLite) e telas refatoradas de `prototype/` | **Não importar / Adiar** | Produto mantém runtime stateless e recuperação lexical determinística (`ADR 0007`), TTS neural e memória de sessão ficam fora do escopo do backend atual. |

## 3. Validações no Consumidor e Reversão

- **Validações Backend:** `ruff format --check`, `ruff check`, `mypy --strict`, `bandit -ll`, `pytest` offline (incluindo `test_pharmacy_stock.py`, `test_infosaude_sync.py`, CORS/CORP em `test_contrato_dast.py` e campos de autocomplete em `test_prescriptions_api.py`), `eval-test`, `eval`, `benchmark`, `seguranca-smoke` e `smoke_http.py`.
- **Validações Mobile (`.github/workflows/mobile-ci.yml`):** Node `22`, `npm ci`, `npx tsc --noEmit` e `npx eslint src`.
- **Reversão:**
  ```bash
  # Na própria branch feat/semana6-base-integracao, reverter toda a portação acima de fix/semana4-calibracao-e-revisao (4197613):
  git revert 4197613..7c3bb71
  # ou descartar a branch feat/semana6-base-integracao mantendo fix/semana4-calibracao-e-revisao @ 4197613
  ```

A reversão acima fixa somente os dois commits já registrados da base Semana 6. As correções posteriores ainda locais devem ser preservadas em patch antes de qualquer reversão; após integração, registrar e reverter o SHA real do PR de correções, sem intervalo aberto até `HEAD`.

O bot serializa execuções, preserva PR sem mudanças materiais e fecha proposta obsoleta quando a fonte volta à base. Publicação usa lease com SHA remoto explícito. PRs criados pelo `GITHUB_TOKEN` exigem aprovação da execução dos checks conforme configuração do GitHub; merge não substitui rebuild/redeploy.

## Fechamento das correções — 2026-11-26

- 579 testes backend com conexões externas bloqueadas; 4 testes de evals. Ruff lint/format (157 arquivos), Mypy (149 arquivos), TypeScript e ESLint aprovados.
- Golden Sets v1/v2: 16/16 e 22/22, Hit@3 e MRR 1,0. Guardrail: recall 100%, falso bloqueio 0% no conjunto executado. Smoke sintético de comparação: 0 pares inválidos, RAGAS/factualidade explicitamente não avaliados. Esses resultados não aprovam geração LLM.
- Docker `sus-cidadao-backend:review-s6`: build aprovado; smoke HTTP completo em container com `PORT=8087`, health interno e regressão de estoque antigo aprovados; container temporário removido.
- No snapshot real, omalizumabe 150 mg em Asa Sul preserva `05/11/2026 13:45:15` e agora retorna `updated_at=2026-11-05T16:45:15+00:00`, `stale_warning=true`.
- Workflow: YAML e sintaxe Bash validados; política coberta por testes. Script de publicação exercitado com Git real em repositório temporário e `gh` simulado: criação A→B, preservação B→B, atualização B→C, fechamento no retorno à base A. Nenhuma publicação real foi executada.
- Pendências para integração: commit/PR das correções, CI remoto e revisão do squad; validar uma execução real do sincronizador e suas permissões. A avaliação v8 continua reprovada em Faithfulness (0,8833 < 0,92), sem revisão humana. Integração visual mobile e deploy permanecem no escopo seguinte.
