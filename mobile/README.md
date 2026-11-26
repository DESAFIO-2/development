# SUS Digital — Base Mobile (`mobile/`)

Base React Native (**Expo SDK 58 + NativeWind + TypeScript**) portado do repositório `DESAFIO-2/Front-End-` para integração oficial com o backend FastAPI de `development/backend/` (ADR 0002).

## Estado Atual (Pronto para Handoff ao Especialista de Front-End)

- **Interface, navegação e design system prontos:** telas `(auth)/login`, `(auth)/cadastro`, `(tabs)/inicio`, `(tabs)/farmacias`, `(tabs)/remedios`, `(tabs)/receitas`, `(tabs)/zelo`, `notificacoes`, `perfil`, `alerta-pulseira` e notificações locais (`expo-notifications`).
- **Cliente HTTP tipado pronto em [`src/services/api.ts`](src/services/api.ts):** contratos 100% alinhados ao OpenAPI real de `backend/app/api/`:
  - `checkHealth` (`GET /health`)
  - `autocompleteMedications` (`GET /api/v1/medications/autocomplete` — incluindo `via_retirada` e `exige_lme`)
  - `auditPrescription` (`POST /api/v1/prescriptions/audit`)
  - `orchestrateAgents` (`POST /api/v1/agents/orchestrate` — recomendado para o chat Zelo)
  - `orchestrateMultimodal` (`POST /api/v1/agents/multimodal` — upload em memória de PDF digital + áudio + `confirmado_pelo_usuario`)
  - `fetchNearbyPharmacies` (`GET /api/v1/pharmacies/nearby`)
  - `fetchCeafStock` (`GET /api/v1/ceaf-stock` — Alto Custo CEAF com `stale_warning` > 48 h e `cobertura_ubs_disponivel: false`)
- **Telas ainda em dados de exemplo (`src/data/mock.ts`):** a substituição dos mocks nas telas pelo SDK `src/services/api.ts` e a bateria interativa E2E de UI são responsabilidade da frente de **Front-End**.

## Mapa de Integração para o Especialista de Front-End

1. **`(tabs)/receitas.tsx`:**
   - Usar `autocompleteMedications` ao digitar itens da receita.
   - Para receita digital em PDF (`expo-document-picker` no nativo / `<input type="file">` na web), enviar via `orchestrateMultimodal`.
   - **Regra obrigatória (`requer_confirmacao_usuario`):** se a resposta retornar `requer_confirmacao_usuario === true`, exibir `candidatos_extraidos` + `opcoes_autocomplete` para o cidadão confirmar/selecionar antes de reenviar `confirmado_pelo_usuario: true` e `itens`.
   - Manter foto/câmera apenas na Carteira Digital local (ADR 0002 — nunca enviar foto de receita manuscrita para OCR).
2. **`(tabs)/zelo.tsx`:**
   - Chat por texto via `orchestrateAgents` (modelo **100% stateless**: reenviar `itens`, `regiao_administrativa` e `pergunta_adicional`; histórico de conversa fica no `app-state.tsx`), renderizando `card`, `resposta_adicional` (quando houver gerador LLM ativo) e `citacoes`.
   - Áudio de voz via `orchestrateMultimodal` (`audioFile` / `audioBlob`), tratando bloqueios clínicos (`BLOQUEADO` -> SAMU 192 / UPA 24h) e abstinência (`NAO_PADRONIZADO`).
3. **`(tabs)/farmacias.tsx`:**
   - Consumir `fetchNearbyPharmacies` (por `ra` ou `lat`/`lng` quando GPS permitido) e `fetchCeafStock`.
   - Exibir claramente `updated_at`, alerta quando `stale_warning === true` (> 48 h) e `aviso_cobertura` informando que o estoque ao vivo cobre **somente Farmácias de Alto Custo (CEAF-DF)** e não UBSs.

## Como Rodar Localmente

Requisitos: **Node 22.13+**, `npm` e o backend FastAPI rodando na raiz (`make run-api`, com `APP_CORS_ORIGINS` já liberando `localhost:8081` e `127.0.0.1:8081` para Expo Web).

```bash
cd mobile
cp .env.example .env
npm install
npx expo start
```

Checagens estáticas:

```bash
cd mobile
npx tsc --noEmit
npx eslint src
```
