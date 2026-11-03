# ADR 0001: Adoção de Clean Architecture (src-layout) e Recuperação Híbrida para o RAG do SUS Cidadão

* **Status:** Aprovado
* **Data:** 2026-11-03
* **Decisores:** Samuel de Souza Rodrigues (AI Engineer / Tech Lead), Mickeias Paiva (Arquiteto de Software), Marlon Marques (Cientista de Dados), Jhiovana Ribeiro (Engenheira de Dados), Tayrine Zitkoski (MLOps/LLMOps)

---

## 1. Contexto e Problema
O projeto **SUS Cidadão (Challenge 2)** tem a missão de apoiar a tomada de decisão do paciente do SUS na obtenção 100% gratuita de medicamentos e exames no Distrito Federal.
O sistema precisa garantir:
1. **Determinismo:** Nomes de princípios ativos (DCB) e coberturas binárias (CBAF, CEAF, Farmácia Popular) não podem ser deduzidos probabilisticamente por uma LLM pura;
2. **Desacoplamento:** A lógica de negócio e os guardrails não devem depender de bibliotecas específicas de banco vetorial (ChromaDB), provedor de LLM ou framework web (FastAPI);
3. **Auditabilidade e Data Lineage:** Toda resposta deve citar a portaria oficial vigente (RENAME 2024, Farmácia Popular, REME-DF, SISREG), com manifesto rastreável de ingestão.

---

## 2. Decisões Técnicas

### 2.1. Adoção do Padrão `src-layout` com Pacote Canônico `challenge2`
Estruturar o código sob `src/challenge2/` seguindo a recomendação da PyPA. Isso garante imports inequívocos (`from challenge2.domain.prescription import Prescription`), isolamento em testes e compatibilidade com empacotamento moderno via `pip` e `uv`.

### 2.2. Separação de Camadas: Domain, Application e Infrastructure
* **Domain (`domain/`):** Modelos e regras de negócio puras (entidades `Prescription`, `Medication`, `AccessRoute`, `CitizenGuidance`). Zero dependência de frameworks externos.
* **Application (`application/`):** Casos de uso (`use_cases/audit_prescription.py`), orquestração de serviços e portas abstratas (`ports/` para repositórios e provedores de IA).
* **Infrastructure (`infrastructure/`):** Implementação concreta dos adaptadores (bancos relacionais, ChromaDB, HuggingFace embeddings, APIs de LLM).
* **Presentation (`api/` e `ui/`):** FastAPI para a API e Streamlit para o protótipo de validação cidadã.

### 2.3. Estratégia de Busca Híbrida (Hybrid Retrieval)
* **Camada Determinística:** Consulta exata por princípio ativo (DCB) e dosagem em tabela canônica para verificar presença no elenco da Farmácia Popular ou REME-DF.
* **Camada Semântica (Vetorial):** Busca vetorial densa em chunks de portarias, notas técnicas e protocolos SISREG (com embeddings multilíngues como BGE-m3).
* **Camada de Síntese Cidadã:** LLM atua exclusivamente na redação clara, acolhedora e estruturada, ancorada no contexto recuperado e bloqueada para prescrição clínica.

### 2.4. Evolução Incremental para Multiagentes (Alinhamento com o Roadmap)
* **Semanas 2 e 3:** O pipeline opera de forma puramente determinística e modular através de Casos de Uso na camada `application/`.
* **Semana 4 (Entregável Multiagentes):** Os agentes especializados (Extrator, Auditor Farmacêutico, Consultor SISREG e Sintetizador) serão construídos como orquestradores sobre os Casos de Uso já validados, prevenindo complexidade prematura nas primeiras semanas.

---

## 3. Consequências e Benefícios
* **Facilidade de Testes:** Casos de uso podem ser testados com mocks de portas em milissegundos sem chamadas de API.
* **Segurança e Ética:** A LLM não tem autonomia para inventar coberturas; ela apenas traduz evidências validadas deterministicamente.
* **Conformidade com o Edital:** Atendimento integral às 5 restrições obrigatórias do Edital do Instituto Eldorado.
