# SUS Cidadão — Backend API

> **API em FastAPI e Motor de Recuperação Híbrida do SUS Cidadão**  
> *Challenge 2: Qualidade de Vida e Tomada de Decisão com IA* — **Instituto Eldorado / UnB / Softex / MCTI**

---

## 1. Visão Geral da Arquitetura

O backend do **SUS Cidadão** foi construído seguindo rigorosamente os padrões da **Clean Architecture** e a filosofia **Ponytail** (simplicidade impiedosa, zero dependências inúteis, máxima resiliência e desempenho previsível).

### Estrutura de Pastas (`backend/app/`):

```text
backend/app/
├── main.py                  # Entrypoint da aplicação FastAPI
├── core/                    # Configurações com Pydantic Settings e telemetria
├── domain/                  # Entidades e modelos puros de negócio (Prescription, Guidance, Medication)
├── application/             # Casos de uso e portas abstratas (Clean Architecture)
│   ├── ports/               # Contratos abstratos (RetrieverPort, MedicationRepositoryPort, etc.)
│   └── use_cases/           # AuditPrescriptionUseCase (orquestração do fluxo em 4 etapas)
├── infrastructure/          # Adaptadores concretos (ChromaDB, repositórios em JSON/memória)
│   ├── persistence/         # Repositórios concretos do catálogo canônico e chunks normativos
│   └── vectorstores/        # ChromaVectorStoreAdapter (multi-coleções)
├── retrieval/               # Motor de Recuperação Híbrida (Tabular DCB + BM25Okapi + TF-IDF RRF)
├── guardrails/              # Preservação do Ato Médico (Lei 12.842/2013) e Mascaramento LGPD (PII)
├── ingestion/               # Pipelines de extração da RENAME 2024 e cliente InfoSaúde-DF (Power BI)
└── api/                     # Camada de apresentação REST (rotas, schemas e dependências)
    └── routes/              # /health e /api/v1/prescriptions
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
