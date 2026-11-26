# SUS Cidadão — Backend API

> **API em FastAPI e Motor de Recuperação Híbrida do SUS Cidadão**  
> *Challenge 2: Qualidade de Vida e Tomada de Decisão com IA* — **Instituto Eldorado / UnB / Softex / MCTI**

---

## 1. Visão Geral da Arquitetura

O backend do **SUS Cidadão** foi construído seguindo rigorosamente os padrões da **Clean Architecture** e a filosofia **Ponytail** (simplicidade impiedosa, zero dependências inúteis, máxima resiliência e desempenho previsível).

### Estrutura de Pastas (`backend/app/`):

```text
backend/app/
├── main.py                  # Entrypoint da aplicação FastAPI + lifespan
├── container.py             # Composição de dependências e instância única de TabularDCBMatcher
├── core/                    # Configurações com Pydantic Settings, logs JSON e telemetria OTel
├── domain/                  # Entidades e modelos puros de negócio (Prescription, Guidance, Medication)
├── agents/                  # Grafo LangGraph (triagem, auditoria, normas, síntese) e CLI demo
├── application/             # Casos de uso e portas abstratas (Clean Architecture)
│   ├── ports/               # Contratos e DTOs desacoplados (RetrieverPort, GuardrailPort, GeneratorPort, etc.)
│   └── use_cases/           # Triagem, auditoria de receitas, consulta normativa e síntese cidadã
├── infrastructure/          # Adaptadores concretos (repositórios em JSON e adaptadores REST LLM)
│   ├── llm/                 # GeminiRESTGeneratorAdapter e OllamaRESTGeneratorAdapter
│   └── persistence/         # Repositórios concretos do catálogo canônico, evidências e chunks normativos
├── retrieval/               # Motor de Recuperação Híbrida (Tabular DCB + BM25Okapi + TF-IDF RRF)
├── guardrails/              # Preservação do Ato Médico (Lei 12.842/2013) e Mascaramento LGPD (PII)
├── seguranca/               # Esteira anti-injection, validação de contexto, PDF/áudio e saída
├── ingestion/               # Pipeline determinístico de consolidação do corpus
└── api/                     # Camada de apresentação REST (rotas, middleware e schemas)
    └── routes/              # /health, /api/v1/medications/autocomplete, /prescriptions/audit e /agents/orchestrate
```

---

## 2. Requisitos & Instalação

O projeto utiliza o **[uv](https://docs.astral.sh/uv/)** para gerenciamento de dependências ultrarrápido e determinístico.

```bash
# 1. Instalar dependências no ambiente virtual isolado (Python 3.12)
cd backend
uv sync

# 2. Configurar variáveis de ambiente (opcional para execução local)
cp .env.example .env
```

---

## 3. Executando a API Localmente

```bash
# Iniciar a API em modo de desenvolvimento com hot-reload:
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Swagger UI interativo:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Healthcheck:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 4. Endpoints Principais da API

### `POST /api/v1/prescriptions/audit`
Audita os itens de uma receita médica prescrita e retorna o roteiro estruturado de retirada gratuita no SUS, validade normativa e bases legais.

* **Exemplo de Payload (JSON):**
  ```json
  {
    "itens": [
      {
        "nome_digitado": "Losartana Potássica 50mg",
        "concentracao": "50mg",
        "forma_farmaceutica": "comprimido"
      },
      {
        "nome_digitado": "Metformina 850mg",
        "concentracao": "850mg"
      }
    ],
    "data_emissao": "2026-11-06",
    "regiao_administrativa": "Ceilândia",
    "tipo_prescritor": "SUS"
  }
  ```

* **Exemplo de Resposta:**
  ```json
  {
    "sucesso": true,
    "regiao_administrativa": "Ceilândia",
    "itens": [
      {
        "medicamento": "Losartana Potássica 50mg",
        "principio_ativo_dcb": "LOSARTANA POTÁSSICA",
        "via_retirada": "FARMACIA_POPULAR",
        "local_sugerido": "Drogarias privadas credenciadas ao Farmácia Popular em Ceilândia ou nas farmácias das UBSs do DF.",
        "o_que_levar": [
          "Receita médica válida com CRM legível",
          "Documento oficial com foto",
          "CPF do paciente"
        ],
        "dias_validade_receita": 180,
        "dias_restantes": 180,
        "citacao_normativa": "PFPB_2024 (p. 14)"
      }
    ],
    "resumo_acolhedor": "Auditamos 2 item(ns) da sua receita para a região de Ceilândia...",
    "aviso_preservacao_ato_medico": "Aviso Importante: Este sistema atua exclusivamente na orientação logística e administrativa de acesso ao SUS..."
  }
  ```

### `GET /api/v1/medications/autocomplete?q=losartana&limite=10`
Fornece sugestões assistidas instantâneas de medicamentos padronizados na RENAME.

---

## 5. Suíte de Testes e Checagens de Qualidade

Execute os mesmos comandos validados no pipeline de Integração Contínua (CI):

```bash
# 1. Executar testes automatizados (unitários, integração e segurança)
uv run pytest

# 2. Verificação estrita de tipagem estática (Mypy strict)
uv run mypy app tests

# 3. Linter e análise de segurança (Ruff)
uv run ruff check .

# 4. Formatação de código
uv run ruff format .
```

---

## 6. Docker

```bash
# Construção da imagem otimizada com usuário não-root:
# Execute a partir da raiz do repositório
docker build -t sus-cidadao-backend -f backend/Dockerfile .

# Execução do container:
docker run --rm -p 8000:8000 sus-cidadao-backend
```

## Agentes da Semana 4

Nova rota `POST /api/v1/agents/orchestrate`: quatro nós LangGraph, execução stateless,
auditoria determinística e geração opcional via `GeneratorPort`. A rota de auditoria
anterior permanece disponível. Sem frontend nesta entrega.

Execute `uv run python -m app.agents.demo` de `backend/` (ou `make demo-agents` da raiz).
O padrão é `APP_AGENTS_PROVIDER=deterministic`. Para Ollama local, configure esse
campo como `ollama` e `APP_AGENTS_MODEL=qwen3.5:4b` (com `GeminiRESTGeneratorAdapter`
pronto para troca via `APP_AGENTS_PROVIDER=gemini` e `APP_GOOGLE_API_KEY`). A
execução `--strict` falha sem gerador ou quando a geração é rejeitada; fixtures não
são evidência científica.

Responsabilidades, diagrama, contratos, modelos, limites, testes e operação:
[guia dos agentes](../docs/architecture/agentes_semana4.md).

## 7. Prontidão de Deploy (LLMOps / MLOps) & Estoque CEAF

- **Porta dinâmica & Docker (`backend/Dockerfile`):** a imagem inclui os snapshots `data/processed/ceaf_live_stock.json` e `df_pharmacies_geolocated.json` e sobe via `${PORT:-8000}` (`--host 0.0.0.0`), com `HEALTHCHECK` apontando para `GET /health`.
- **CORS & Web (`APP_CORS_ORIGINS`):** origens liberadas para o cliente Expo Web (padrão local `http://localhost:8081,http://127.0.0.1:8081`); requisições sem `Origin` autorizada mantêm `Cross-Origin-Resource-Policy: same-origin` (compatível com ZAP/Schemathesis).
- **Troca de provedor LLM em produção:** o código já isola `GeneratorPort`. Para sair do modo `deterministic` ou `ollama` (`qwen3.5:4b`) para uma API na nuvem sem alterar código, basta configurar `APP_AGENTS_PROVIDER=gemini`, `APP_AGENTS_MODEL=<modelo-flash>` e `APP_GOOGLE_API_KEY`.
- **Áudio / STT no deploy (`APP_STT_PROVIDER`):** padrão `disabled`. Em container com >= 1–2 GB RAM (ex.: Cloud Run), usar `--extra stt` (`faster_whisper` + `base`); em planos <= 512 MB RAM, usar `APP_STT_PROVIDER=whisper_http` apontando para endpoint `/v1/audio/transcriptions` compatível.
- **Rotas de farmácias & estoque (`backend/app/api/routes/pharmacies.py`):** `GET /api/v1/pharmacies/nearby` e `GET /api/v1/ceaf-stock` sanitizam parâmetros ecoados (`ra`, `query`, `unidade`) contra PII, ordenam estritamente por menor distância quando recebem GPS (`lat`/`lng`), mantêm `cobertura_ubs_disponivel=false` e calculam `updated_at` e `stale_warning` por item a partir de `ultima_atualizacao` da fonte. Data ausente, inválida, futura ou antiga (> 48 h) exige alerta. No resumo, `updated_at` é a menor data entre todos os resultados filtrados (nulo se algum não tem data ou não há resultados); `stale_warning` é verdadeiro se qualquer resultado exige alerta, inclusive além do limite da página. `panel_updated_at_utc` é somente metadado do painel e `synced_at_utc` informa a coleta. Os snapshots são embutidos na imagem Docker e carregados uma vez em memória por processo; atualizações feitas via `PYTHONPATH=backend uv run --project backend python -m app.ingestion.infosaude_sync --output-dir data/processed` (ou PR automático de `.github/workflows/infosaude-stock-sync.yml`) exigem merge + rebuild/redeploy para refletir em produção.
