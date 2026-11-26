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
| `Data-Science/data/gold/{ceaf_live_stock,df_pharmacies_geolocated}.json` (`677cd37`) | **Importar** | `ceaf_live_stock.json` atualizado em `data/processed/` (`857` registros CEAF de `2026-11-25T19:05:59+00:00`); `df_pharmacies_geolocated.json` verificado idêntico (`231` estabelecimentos / `174` geolocalizados). |
| `Data-Science/src/sus_cidadao_ds/ingestion/infosaude_client.py` + `.github/workflows/infosaude-stock-sync.yml` | **Adaptar** | Reimplementado sem dependências externas em `backend/app/ingestion/infosaude_sync.py` (apenas stdlib `urllib.request` com trava HTTPS + decoder DSR), adicionando query `Estabelecimentos` baseada em `data-engineering/src/ingestion/infosaude_live.py` e workflow `.github/workflows/infosaude-stock-sync.yml`. |
| `Data-Science/src/sus_cidadao_ds/agents/ports.py` (`PharmacyRepositoryPort.find_nearby`) + rotas `/v1/pharmacies/nearby`, `/v1/ceaf-stock` | **Adaptar (Clean Architecture)** | Contratos em `backend/app/application/pharmacy_stock.py`, repositório `LocalPharmacyStockRepository` reusando `normalizar_texto_pt`, correção do filtro estrito por `ra`/`q` (CEAF não vaza para buscas de outra RA), cálculo de `stale_warning > 48 h`, explicitação de `cobertura_ubs_disponivel=false`, e rotas `/api/v1/pharmacies/nearby` e `/api/v1/ceaf-stock` com validação OpenAPI (`math.isfinite`). |
| `Data-Science` ChromaDB, `/v1/tts`, `/v1/sessions` (memória SQLite) e telas refatoradas de `prototype/` | **Não importar / Adiar** | Produto mantém runtime stateless e recuperação lexical determinística (`ADR 0007`), TTS neural e memória de sessão ficam fora do escopo do backend atual. |

## 3. Validações no Consumidor e Reversão

- **Validações Backend:** `ruff format --check`, `ruff check`, `mypy --strict`, `bandit -ll`, `pytest` offline (incluindo `test_pharmacy_stock.py`, `test_infosaude_sync.py`, CORS/CORP em `test_contrato_dast.py` e campos de autocomplete em `test_prescriptions_api.py`), `eval-test`, `eval`, `benchmark`, `seguranca-smoke` e `smoke_http.py`.
- **Reversão:**
  ```bash
  git revert <SHAS_SEMANA6>
  # ou descartar a branch feat/semana6-base-integracao mantendo fix/semana4-calibracao-e-revisao
  ```
