# ADR 0004 — Integridade do comparativo da semana 3

- Status: implementado nesta branch; avaliação científica pendente.
- Data: 2026-11-11.
- Complementa ADR 0003; não reduz suas metas.

## Contexto

O comparativo usava respostas sintéticas como se fossem medidas de modelos e
heurísticas lexicais como RAGAS. O fallback ocultava falhas e a identidade do
provedor era inferida por uma chamada separada. A API também descartava filtros
quando recebia múltiplas doses e aplicava um limite de texto à receita inteira.

## Decisão

1. Clientes REST só produzem resposta do provedor ou erro explícito. O DTO registra
   origem, erro e latência. Controles da aplicação são identificados separadamente.
2. Baseline sintético somente em `evals/baselines`, selecionado explicitamente.
   Sem respostas pré-escritas para demonstrar superioridade do RAG.
3. O runner persiste metadados por caso, invalida pares com falha ou provedores
   incompatíveis e nunca mistura a pergunta/gabarito às evidências do avaliador.
4. Citações têm validação estrita de metadados, sem inferência de verdade factual.
   Heurísticas recebem nomes próprios. RAGAS/factualidade não medidos ficam nulos.
5. Metas do ADR 0003 permanecem: 0,92, 0,88, 0,90 e 0,88. Nenhum resultado ausente
   satisfaz a entrega. A CI testa o protocolo, não qualidade de modelo real.
6. A API inspeciona campos individualmente, preservando prioridade de emergência;
   concentrações ambíguas ou conflitantes provocam abstenção. Denominadores como
   `250 mg/5 mL` são reconhecidos integralmente, sem inferir equivalência clínica.
7. Fixtures HTTP de perguntas com vários medicamentos usam itens separados;
   recuperação e geração mantêm a pergunta original e nenhum gabarito é alterado.

## Consequências e reversão

Relatórios antigos do commit 9912090 ficam invalidados como evidência científica.
A geração real exige configuração explícita de modelo. A coleta não aprova o
entregável sem RAGAS e revisão factual. SDKs de avaliação ficam em `evals/`, com
lockfile próprio; o lockfile da API permanece inalterado.
Para reverter tecnicamente, restaurar os arquivos de aplicação, runner, fixtures,
CI e documentação juntos a partir de 9912090; isso reintroduz os defeitos conhecidos
 e não autoriza republicar suas conclusões como resultados reais.

## Endurecimento operacional de 2026-11-11

- Coleta com checkpoint atômico por braço e identidade de código/dataset/corpus/modelo.
  Resposta persistida, inclusive erro, nunca é substituída na retomada.
- Avaliação com um event loop por cliente assíncrono, cache por métrica/par e
  histórico de tentativas. Retentativas explícitas limitadas a três por par.
- Consolidação offline não instancia cliente nem regenera escores. Cada versão
  do relatório preserva a auditoria correspondente.
- Auditoria v2 vinculada aos hashes da coleta, dos casos e das respostas. Inclui
  todas as respostas, separando agregados de LLM e controles. Contagens inteiras;
  zero afirmações é válido e produz taxa nula, com justificativa do revisor.
- Contradição e não verificabilidade permanecem distintas. Proporção não confirmada
  não recebe o nome de taxa de erro factual.
- Saída da avaliação: 0 completo/aprovado, 1 incompleto, 2 completo/reprovado,
  3 auditoria pendente ou piloto. Saída 0 do orquestrador indica apenas inferência
  concluída e imprime explicitamente o status científico.
- Testes do ambiente isolado exercitam o SDK e as quatro métricas oficiais com
  HTTP simulado. Não constituem evidência sobre qualidade do modelo local.
