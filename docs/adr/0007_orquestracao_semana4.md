# ADR 0007 — Orquestração delimitada da Semana 4

- Data: 17/11/2026 (revisado em 19/11/2026).
- Status: implementado na `main`; coleta comparativa local com Ollama concluída em `semana4-v2` (RAGAS exploratório realizado; gates integrais e revisão factual humana pendentes).
- Complementa ADRs 0001, 0002, 0004 e 0006; não altera metas científicas.

## Decisão

Adotar LangGraph como adaptador fino em `backend/app/agents/`, com contratos e
síntese em `application/`. Quatro responsabilidades explícitas, das quais três
determinísticas. Não são quatro LLMs autônomas: trata-se de workflow especializado
com uma chamada generativa opcional. Essa escolha mantém as decisões de cobertura,
concentração, validade e documentos reproduzíveis e auditáveis.

A topologia proposta no protótipo de Marlon é adaptada: triagem precede o fan-out
auditoria/normas, com barreira dos dois ramos antes da síntese. Nós não instanciam
adaptadores nem resolvem credenciais. `ServiceContainer` compõe portas existentes.
`/api/v1/prescriptions/audit` preserva o fluxo e contrato; a nova rota é aditiva.

Sem memória entre requisições, SQLite, checkpointer ou herança implícita de tópico.
O cliente precisa reenviar os itens relevantes. Isso evita os defeitos de mistura
de tópicos do protótipo e reduz dados persistidos. Sessões são uma decisão futura
com finalidade, retenção, exclusão e testes próprios.

O Agente 2 reutiliza a auditoria existente e liga a apresentação selecionada às
evidências por `occurrence_ids`; não rematcheia nomes nem usa identidade de DS
como se fosse identidade canônica. O Agente 3 recupera regras para a dúvida
administrativa. O fallback SISREG de itens de exame permanece na auditoria
existente para não duplicar a decisão de rota em dois componentes.

## Modelo e integridade

Modo padrão `deterministic`, declarado na resposta, sem simulador. Ativação de
Ollama/Gemini é explícita e não depende apenas da presença de chave. O candidato
operacional local desta semana é Qwen2.5 7B; 14B é o comparador de maior capacidade
no MacBook. A escolha final exige execução no hardware alvo: a medição anterior
de 14B (~22 s) não atende à meta de 8 s. Não prometer velocidade ou qualidade do 7B
sem medição. Modelo leve 1.5B serve somente para smoke de transporte, se necessário.

Prompt versionado `semana4-v2` (evoluído de `semana4-v1`), separado do protocolo congelado `semana3-v3`: quando há `pergunta_adicional`, o contexto enviado ao gerador prioriza `normative_hits` para evitar abstenção indevida, a resposta da LLM fica isolada em `resposta_adicional` mantendo o `card` 100% determinístico, e código monta cartões e citações. Na coleta local com Ollama (`qwen2.5:7b` e `qwen2.5:14b`), `semana4-v2` zerou falhas e rejeições nos 5 casos planejados, mas a latência `p95` local (17,87 s no 7B e 37,28 s no 14B) ainda ficou acima da meta `RNF04` (`<= 8 s`) na rodada observada; sem isolamento experimental do efeito de cold-start. A quantidade de
contexto é limitada e os IDs efetivamente enviados são registrados. Testes com
fakes ficam exclusivamente em `tests/`. Falhas geram metadados explícitos; `strict`
levanta `GenerationFailure` com latência/erro e não produz resposta substituta.
O runner científico da Semana 3 não é modificado nem confundido com o grafo novo.

## Limites e consequências

- A validação de saída verifica PII, posologia/troca e metadados de citação. Não
  comprova sustentação factual da prosa: RAGAS e revisão humana continuam exigidos.
- Contexto recuperado passa pelos controles existentes antes do modelo e da
  exibição literal. Reprovação é explícita (`CONTEXTO_REJEITADO`); não é erro do
  provedor. O bloqueio conservador de CID em texto normativo é limitação conhecida.
- Citação de evidência literal comprova presença na edição congelada; não prova
  estoque, elegibilidade, vigência atual ou todos os requisitos operacionais.
- Sem ativação de estoque/geolocalização nesta entrega: snapshots requerem regra
  de frescor e validação de produto. Não criar interfaces ainda sem uso.
- LangGraph acrescenta dependências transitivas; versão resolvida no lockfile.
  LangSmith tracing desabilitado no invoke, mesmo sob configuração ambiente.
  Telemetria OTel própria não registra payloads. Sem persistência de estado do grafo.
- Paralelismo é concorrência do workflow; não é promessa de aceleração de CPU Python.
- Contexto omitido por orçamento não altera os cartões; todos os vínculos continuam
  disponíveis na resposta. Modelo não precisa receber 50 itens para auditá-los.

Reversão: reverter a unidade de integração do grafo, rota, composição e dependências,
conforme [registro de portação](../implementation/portacao_agentes_semana4.md).


## Avaliação e observabilidade — correção de 19/11

A rubrica `semana4-eval-v2` exige cinco cenários distintos e conhecidos; métricas
não avaliadas não satisfazem gates. Qualidade automatizada, latência RNF04 e
revisão humana permanecem dimensões separadas. O runner retorna 1 para avaliação
incompleta, 2 para reprovação e 3 quando os gates automáticos passam, mas falta
revisão humana. Smoke sintético retorna 0 apenas como teste de protocolo.

Resultados da rubrica v1 são históricos, não recalculados nem sobrescritos.
A nova instrução do juiz limita completude ao pedido do cidadão e exige conferência
literal antes de apontar omissão; isso requer nova medição, não prova melhora.
Backfills MLflow não atribuem o manifesto de importação à execução histórica.
Reversão dessas correções deve manter relatórios e seus manifestos originais;
reverter código não autoriza declarar aprovação dos antigos gates permissivos.

## Convergência operacional local (`qwen3.5:4b`, `semana4-v3`, `semana4-eval-v3`)

Após a rodada histórica em `qwen2.5:7b` e `qwen2.5:14b`, a calibração com `warmup()`
explícito, `think=False` automático em `qwen3.5*`, foco de localização
(`_focused_generation_candidates`), prompt `semana4-v3` e juiz `semana4-eval-v3`
(`num_predict=900`, suporte `--models` em `semana4_avaliacao.py`) convergiu o candidato
local para **`qwen3.5:4b`** (rodada `evals/reports/semana4_comparativo_v8`):
- **Desempenho (`RNF04 <= 8 s`):** warmup `378,41 ms`, mediana `5.006,42 ms`,
  `p95 = 5.329,77 ms` (**aprovado**, vs. `9,05–19,08 s` no `7B` e `33,86 s` no `14B`).
- **Controles & Juiz Estruturado (`qwen2.5:14b`):** determinístico `10,00/10` (`5/5`,
  `0` falhas), nota do juiz `9,39/10` (`0` contradições, `0` não verificáveis, `1`
  omissão parcial apontada em `procuracao_fralda`).
- **RAGAS (`0.4.4` + `bge-m3`):** `Answer Relevancy = 0,9484 >= 0,88` (**aprovado**) e
  `Faithfulness = 0,8833` (vs. `0,900` na rodada `v6` com `Juiz = 9,9/10`; oscilação
  do NLI local Q4 e revisão factual humana clínica permanecem explicitadas, sem baixar
  o gate `0,92`).
- **Produto (`backend/app/core/config.py`):** mantém `APP_AGENTS_PROVIDER=deterministic`
  como padrão seguro offline/CI, `APP_AGENTS_MODEL=qwen3.5:4b` como modelo local
  validado e `GeminiRESTGeneratorAdapter` (`APP_AGENTS_PROVIDER=gemini`) pronto e
  desacoplado para conexão futura em nuvem por MLOps/LLMOps via variáveis de ambiente.
