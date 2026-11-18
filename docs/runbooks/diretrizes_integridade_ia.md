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
  - *API determinística*: catálogo reconciliado de 1.708 apresentações, recuperação lexical e guardrails locais; sem ChromaDB em runtime.
  - *Implementação da Semana 4 nesta branch*: rota aditiva de quatro nós LangGraph, evidência por ocorrência e geração opcional explicitamente configurada. Padrão determinístico, sem memória de sessão. Ver [ADR 0007](../adr/0007_orquestracao_semana4.md).
  - *Avaliação pendente*: qualidade/latência da geração no grafo novo requer coleta real, RAGAS e revisão humana; testes com fakes não satisfazem esse gate.
  - *Roadmap*: multimodalidade/mobile, sessões com retenção definida e estoque com política de frescor. Bases locais de estoque não equivalem a consulta em tempo real.

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
8. [ ] Todos os campos ecoados em respostas bloqueadas, de abstenção ou de fallback (ex.: `regiao_administrativa`, identificadores, mensagens) passam por validação de saída (`validar_saida`) ou normalização segura?
9. [ ] Alterações em regex de guardrail/LGPD incluem testes adversariais de bypass (vírgula na negação, numerais por extenso, caixa baixa após autoidentificação, separadores alternativos) e varredura de falso positivo nas evidências/normas oficiais?
10. [ ] Novos runners em `evals/runners/` usam `bind_manifest`, `source_hashes`, `p95` conservador (`math.ceil`) e possuem testes contra contaminação `synthetic_smoke` vs coleta real?
11. [ ] Fallbacks de recuperação possuem teste negativo com pergunta fora de escopo acompanhada de item válido na requisição?

---

## 4. Post-Mortem Técnico da Semana 4 (Por que os Bugs Escaparam na 1ª Varredura e Como Evitar Repetição)

Na revisão independente pós-PR da Semana 4, quatro defeitos `P1` e quatro melhorias `P2` foram reproduzidos em código que já havia passado em todos os testes unitários e na varredura completa do catálogo (`1.708` itens e `2.114` evidências). Os pontos cegos que explicam por que não apareceram antes — e as proteções permanentes adotadas — são:

1. **Testar apenas o caminho feliz e o catálogo inteiro cria falsa confiança em campos secundários (`P1-1` / `P2-2`)**:
   - *Por que escapou:* os testes de bloqueio e a varredura de catálogo preenchiam `pergunta_adicional` com ataques ou nomes de remédios, deixando `regiao_administrativa` e `tipo_prescritor` com valores benignos. Assim, `_synthesize` no ramo `BLOQUEADO` validou somente `resumo_acolhedor` e deixou `regiao_administrativa` passar sem `validar_saida`; e sinais fracos de injeção divididos entre campos passavam isoladamente.
   - *Regra permanente:* sempre testar payloads adversariais cruzados (*cross-field probing*), injetando conteúdo proibido em **todos** os campos ecoados no cartão final (inclusive em rotas `BLOQUEADO`/`ABSTENCAO`) e agregando famílias de sinais fracos por requisição sem concatenar strings longas.

2. **Confiar apenas nos exemplos positivos/negativos existentes mascarou variações triviais de regex (`P1-2` / `P1-3`)**:
   - *Por que escapou:* a bateria existente só exercitava conjunções adversativas (`mas`), algarismos (`2 comprimidos`, `3 vezes`) e PII capitalizada/padrão. Variações simples — vírgula após `"Não troque,"`, `"duas vezes ao dia"`, `"me chamo joao silva"` em minúscula, espaço após o `9` ou pontos em telefone (`61 9 9999-0000`, `61.99999.0000`), prefixo colado (`fone...`), CPF separado por espaços e CNS com hífens — não tinham sonda de contorno dedicada.
   - *Regra permanente:* ao escrever ou revisar regex de saída/LGPD, executar obrigatoriamente **tentativa explícita de contorno** (pontuação, numerais por extenso, caixa baixa após autoidentificação e separadores alternativos), cuidando para não relaxar preposições ambíguas como `"para o/a"` em minúscula (evitando falso mascaramento de frases comuns como `"para a entrega gratuita"`), e revalidar contra todas as evidências e normas carregadas.

3. **Smoke sintético e testes de fallback sem invariantes negativas de contorno (`P1-4` / `P2-1`)**:
   - *Por que escapou:* os testes de `semana4_comparativo.py` cobriam execução sintética e falha de provedor isoladamente, mas não comparavam o cálculo de `p95` com `ragas_runner.py` (`int(...)` vs `math.ceil(...)`, ocultando outliers em amostras pequenas como `--pilot`), nem testavam colisão de diretório entre `--synthetic-smoke` e coleta real sem `bind_manifest`/`source_hashes`. Em `consult_norms.py`, o fallback com itens foi testado apenas com perguntas válidas, sem testar pergunta totalmente fora de domínio acompanhada de item padronizado.
   - *Regra permanente:* todo runner experimental deve herdar o mesmo padrão de manifesto (`bind_manifest` + `source_hashes` + chave de modo/digest nos checkpoints) e cálculo conservador de latência (`math.ceil`) já adotados em `ragas_runner.py` e `suite_seguranca.py`, acompanhado de testes negativos explícitos para mistura de modos, outliers e consultas fora de escopo com itens presentes.
