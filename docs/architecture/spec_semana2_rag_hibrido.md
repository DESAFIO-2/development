# SPEC-DEV-001: Implementação da Recuperação Híbrida e Guardrails na Clean Architecture

- **Status:** Concluído e Aprovado
- **Fase:** Semana 2 (Base de Conhecimento, Recuperação Híbrida e Rastreabilidade Normativa)
- **Data:** 05/11/2026
- **Responsáveis:** Esquadrão SUS Cidadão (Samuel, Mickeias, Marlon, Jhiovana, Tayrine)
- **Filosofia de Engenharia:** *Ponytail Architecture* (KISS, YAGNI, Zero Asset Bloat, Desacoplamento Limpo, Simpatia Mecânica)

---

## 1. Contexto & Problema

O projeto **SUS Cidadão (NavegaSUS)** necessita orientar pacientes e cuidadores (como *Dona Helena* e *Lucas*) sobre como obter gratuitamente medicamentos e exames no Distrito Federal através do SUS.

A inteligência de recuperação desenvolvida em `DESAFIO-2/Data-Science` provou experimentalmente que:
1. **LLM Pura** alucina em regras locais do DF e inventa coberturas inexistentes (Fidelidade < 40%).
2. **TF-IDF puro** com limiar 0.12 sofre com termos genéricos e falha em abstenção.
3. **RAG Híbrido (Matching Tabular DCB + TF-IDF + BM25 via Reciprocal Rank Fusion)** com limiar calibrado `min_score = 0.18` atinge 100% de precisão de rota e 100% de acurácia de abstenção.

Esta especificação define como transpor essa inteligência para o repositório `DESAFIO-2/development` mantendo a **Clean Architecture** inviolável, sem acoplamento a CLIs monolíticas e com 100% de tipagem estrita no Mypy.

---

## 2. Decisões Arquiteturais (Ponytail Principles)

### 2.1 Ruthless Minimalism & YAGNI
- Nada de wrappers ou orquestradores pesados desnecessários na camada de domínio.
- A lógica de matching determinístico DCB e a fusão de rankings (RRF) devem ser implementadas em Python puro, ultrarrápido, sem dependências volumosas externas.
- O ChromaDB é utilizado como adaptador de persistência vetorial sob uma interface abstrata (`VectorStorePort`), permitindo testes com mocks em memória sem requisições de I/O.

### 2.2 Zero Asset Bloat
- Os PDFs originais ficam em `data/raw/` para permitir que o pipeline extraia seus textos e hashes SHA-256 localmente, mas são **ignorados no Git** (`data/raw/**/*.pdf` no `.gitignore`).
- As tabelas e coleções processadas são persistidas em `data/processed/` e `data/vectorstore/`, com versionamento auditável de hashes em `data/manifests/manifest.json`.

### 2.3 Preservação do Ato Médico & LGPD
- **Camada de Guardrail Clínico (`guardrails/clinical.py`):** Interceptação imediata de pedidos de diagnóstico, prescrição, dosagem e troca de medicamentos (Lei nº 12.842/2013).
- **Camada de Mascaramento PII (`guardrails/pii.py`):** Regex/NER para sanitização de CPF, Cartão SUS (CNS), telefone e e-mail antes de qualquer processamento da LLM (LGPD Art. 11).

---

## 3. Mapeamento de Camadas (Clean Architecture)

```
┌────────────────────────────────────────────────────────┐
│                      API Layer                         │
│  - FastAPI Routes (/api/v1/prescriptions/audit)        │
│  - Autocomplete (/api/v1/medications/autocomplete)     │
└──────────────────────────┬─────────────────────────────┘
                           │ Consome
                           ▼
┌────────────────────────────────────────────────────────┐
│                   Application Layer                    │
│  - Use Cases: AuditPrescription, SearchMedication      │
│  - Ports (Interfaces): VectorStorePort, RetrieverPort, │
│                        StockProviderPort, LLMPort      │
└──────────────┬───────────────────────────┬─────────────┘
               │ Usa                       │ Implementado por
               ▼                           ▼
┌──────────────────────────┐   ┌─────────────────────────┐
│       Domain Layer       │   │   Infrastructure Layer  │
│  - MedicationCoverage    │   │  - ChromaVectorStore    │
│  - PrescriptionAuditReq  │   │  - LocalTabularRepo     │
│  - CitizenGuidanceCard   │   │  - InfoSaudeAPIClient   │
│  - ItemRoteiroCidadao    │   │  - StrictLLMProvider    │
└──────────────────────────┘   └─────────────────────────┘
```

---

## 4. Contratos e Interfaces

### 4.1 `RetrieverPort` (`backend/app/application/ports/retriever.py`)
```python
class RetrieverPort(ABC):
    @abstractmethod
    def search(
        self, query: str, top_k: int = 5, min_score: float = 0.18
    ) -> list[RetrievalHitDTO]: ...
```

### 4.2 `VectorStorePort` (`backend/app/application/ports/vectorstore.py`)
```python
class VectorStorePort(ABC):
    @abstractmethod
    def search_semantic(
        self,
        query: str,
        collection_name: str,
        where_filter: dict[str, Any] | None = None,
        top_k: int = 5,
    ) -> list[SemanticHitDTO]: ...
```

### 4.3 `GuardrailPort` (`backend/app/application/ports/guardrail.py`)
```python
class ClinicalGuardrailPort(ABC):
    @abstractmethod
    def evaluate(self, query: str) -> GuardrailResultDTO: ...
```

---

## 5. Critérios de Sucesso e Verificação da Semana 2
- [ ] Testes unitários do domínio e casos de uso passando no `pytest`.
- [ ] Runner de guardrail atingindo 100% de recall de bloqueio em `evals/datasets/guardrail_clinico_v1.jsonl`.
- [ ] Golden Set integrado em `evals/datasets/golden_set_v1.jsonl` validado no CI.
- [ ] Script de demonstração `evals/runners/demo_rag_runner.py` executando com sucesso os casos de Dona Helena e Lucas.
- [ ] Zero erros no `ruff check` e `mypy app tests evals`.
