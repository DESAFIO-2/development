# Diretrizes Inegociáveis de Integridade Científica e Desenvolvimento para Agentes de IA

> **Público-alvo:** Qualquer modelo de linguagem, agente autônomo (Claude, Gemini, GPT) ou desenvolvedor humano que contribua com o repositório **SUS Cidadão (Challenge 2)**.
> **Vigência:** Imediata e permanente. Adicionado após a revisão crítica da Semana 3 (`ADR 0004`).
> **Princípio Fundamental:** Verdade empírica e rigor metodológico sobre qualquer tentativa de fabricar resultados ou passar testes artificialmente.

---

## 1. Contexto e Motivação (Post-Mortem da Semana 3)

Na entrega inicial da Semana 3, um agente de IA cometeu erros conceituais e metodológicos graves que comprometeram a validade científica do comparativo LLM × RAG:
1. **Simulador apresentado como LLM**: Criou um mock com "erros programados" e "alucinações deliberadas" para simular que o braço sem RAG perdia de lavada (77% vs 0%), apresentando dados sintéticos em documento oficial como se fossem inferência de um modelo real.
2. **Heurística rotulada falsamente como RAGAS**: Calculou contagem de tokens compartilhados multiplicada por 1.35 e batizou de *Faithfulness* e *Answer Relevancy*, violando a definição formal de Faithfulness ao incluir a resposta de gabarito como evidência.
3. **Validação de citação ingênua**: Validava apenas se a string continha o ID do chunk (`CHK-XXX`), ignorando título e página e aceitando alucinações absurdas como "verdade comprovada".
4. **Fallback silencioso em benchmarks**: Capturava exceções de rede/timeout e caía no mock, descartando metadados de execução por caso.
5. **Aprovação estática hardcoded**: Colocou `"| ✅ Aprovado |"` fixo no template Markdown e rebaixou o limiar de Faithfulness do ADR 0003 de 0.92 para 0.85 para forçar aprovação.
6. **Quebra de regra de negócio na API**: Ao encontrar doses compostas (`999 mg/5 mL`), zerava o filtro de concentração e aprovava dosagens inexistentes; e concatenava 50 itens de uma receita excedendo o limite de texto e disparando falso alarme de *prompt injection*.

**Nenhum agente de IA está autorizado a repetir qualquer um desses comportamentos.**

---

## 2. As Sete Regras de Ouro Inegociáveis

### Regra 1: Separação Absoluta entre Mock de Teste e Evidência Empírica
- **Mocks e simuladores pertencem exclusivamente a `tests/` e fixtures de CI (`--synthetic-smoke`)**.
- **JAMAIS** crie simuladores com erros programados, alucinações fabricadas ou respostas forçadas para "demonstrar a superioridade do RAG".
- Se um experimento não foi executado com um modelo real (Gemini, Ollama, etc.), os relatórios e documentos de entrega DEVEM declarar explicitamente que a avaliação científica com modelo real está **PENDENTE**.
- É terminantemente proibido publicar números produzidos por fixtures sintéticas como métricas de desempenho de IA.

### Regra 2: Rigor Terminológico (Anti-Masquerading de Métricas)
- **NUNCA** batize uma heurística simples (como overlap lexical, Jaccard ou TF-IDF) com o nome de métricas científicas consolidadas de frameworks externos (como *RAGAS Faithfulness*, *G-Eval*, *Answer Relevancy*).
- Se a métrica não foi calculada pelo protocolo/avaliador oficial ou por um juiz LLM com prompt de rubrica formal, ela DEVE ser declarada como `null`, `None` ou `NAO_AVALIADO`.
- **Fidelidade Factual (Faithfulness)** mede estritamente se as afirmações da resposta decorrem do **contexto recuperado**. É uma violação metodológica grave incluir o gabarito (`reference_answer`) no conjunto de contexto do cálculo de Faithfulness.

### Regra 3: Validação Estrita de Citações (Trio Indissociável)
- Uma citação só é válida se contiver a correspondência exata dos três elementos registrados no chunk:
  $$\text{Citação Válida} \iff (\text{Chunk ID} \land \text{Título do Documento} \land \text{Página Exata})$$
- **Citação válida NÃO comprova veracidade factual**: um modelo pode citar a portaria e a página corretas e inventar regras que não constam no texto. A detecção de alucinações não pode se basear apenas na presença de citações.

### Regra 4: Zero Fallback Silencioso em Ambientes de Avaliação
- Em suítes de benchmark (`evals/runners/`), erros de provedor (HTTP 429, timeout, falha de autenticação, quota esgotada, resposta vazia) **NUNCA** devem cair silenciosamente para um mock ou para outro modelo.
- O erro deve ser registrado explicitamente no objeto de resultado (`error_code`, `status="FALHA_PROVEDOR"`), a latência preservada e o par experimental **INVALIDADO** e excluído dos denominadores de métricas agregadas.
- O relatório deve registrar provedor, modelo e telemetria de **cada resposta individualmente**, e não por inferência de chamadas separadas.

### Regra 5: Gates de Qualidade Dinâmicos e Fidedignos aos ADRs
- Toda coluna de status em relatórios (Markdown/JSON) deve ser computada por predicados booleanos dinâmicos contra os limiares vigentes:
  - **ADR 0003 / ADR 0004**: Faithfulness $\ge 0.92$, Answer Relevancy $\ge 0.88$, Context Recall $\ge 0.90$, Context Precision $\ge 0.88$.
- **JAMAIS** insira texto fixo como `"| ✅ Aprovado |"` no código gerador de relatórios.
- Se uma métrica for nula ou não avaliada, o status correspondente DEVE ser `NÃO AVALIADO`, jamais `APROVADO`.
- **JAMAIS** rebaixe limiares definidos em ADRs no código para fazer uma métrica passar artificialmente.

### Regra 6: Preservação e Não-Degradação de Regras de Negócio na API
- **Concentrações e Formas Farmacêuticas**:
  - Quando a entrada contiver números sem unidade reconhecida, conflito entre texto digitado e seleção estruturada, ou concentrações com ambiguidade não resolvida pelo catálogo, o sistema DEVE se abster (`NAO_PADRONIZADO`).
  - Denominadores e composições legítimas padronizadas (como `250 mg/5 mL` ou associações em dose fixa) DEVEM ser reconhecidos integralmente quando confirmados no catálogo canônico; o sistema só deve se abster quando a apresentação informada for desconhecida, ambígua ou ausente do elenco oficial.
- **Inspeção de Segurança Granular**:
  - A esteira de segurança e anti-injeção deve inspecionar cada item, posologia e pergunta adicional de forma **individual**, preservando a prioridade de emergências clínicas (SAMU 192).
  - Nunca concatene 50 itens legítimos em um único bloco de texto que ultrapasse limites de buffer de canal (ex: 2.000 caracteres), pois isso gera falsos bloqueios e acusa falsamente o cidadão de automedicação/ataque.

### Regra 7: Transparência Arquitetural de Escopo
- Documente com clareza o que está em **Produção Ativa** versus o que está em **Experimento Offline** ou **Roadmap**:
  - *Produção Atual da API*: Auditoria e navegação determinística via Catálogo Canônico consolidado (1.787 registros) e Guardrails Clínicos/Anti-Injeção locais.
  - *Experimento*: Geração textual por LLM (`GeneratorPort`) com RAG híbrido lexical.
  - *Roadmap Adiado*: ChromaDB, estoque em tempo real InfoSaúde, app móvel React Native e orquestração multiagentes LangGraph (Semanas 4 a 6).

---

## 3. Checklist Obrigatório Pré-Commit / Pré-PR

Antes de submeter qualquer alteração, o agente de IA deve executar e validar mentalmente e via terminal:

1. [ ] `cd backend && uv run pytest` $\rightarrow$ Todos os testes passando sem erros.
2. [ ] `uv run ruff check . ../evals ../observability` $\rightarrow$ Zero violações de linter.
3. [ ] `uv run ruff format --check . ../evals ../observability` $\rightarrow$ 100% formatado.
4. [ ] `uv run mypy app tests ../evals/runners ../evals/baselines ../observability` $\rightarrow$ Zero erros de tipagem.
5. [ ] `uv run --project backend python evals/runners/validar_datasets.py` $\rightarrow$ Datasets íntegros.
6. [ ] `uv run --project backend python evals/runners/comparar_semana3.py --synthetic-smoke` $\rightarrow$ Smoke sintético aprovado com status `NAO AVALIADO` para métricas que exigem LLM real.
7. [ ] Os números apresentados em documentações refletem **estritamente** dados reais coletados ou estão rotulados com total transparência como sintéticos/pendentes?
