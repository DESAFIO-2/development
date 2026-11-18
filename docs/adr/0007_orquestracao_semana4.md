# ADR 0007 — Orquestração delimitada da Semana 4

- Data: 17/11/2026.
- Status: implementado na branch; revisão do squad e avaliação real pendentes.
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

Prompt novo `semana4-v1`, separado do protocolo congelado `semana3-v3`: o modelo
só explica evidências, enquanto código monta cartões e citações. A quantidade de
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
