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
entregável sem RAGAS e revisão factual. Nenhum SDK ou dependência nova foi adicionado.
Para reverter tecnicamente, restaurar os arquivos de aplicação, runner, fixtures,
CI e documentação juntos a partir de 9912090; isso reintroduz os defeitos conhecidos
 e não autoriza republicar suas conclusões como resultados reais.
