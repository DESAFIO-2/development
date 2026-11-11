# Revisão corretiva — Semana 3 — 11/11/2026

Branch: `feat/semana3-comparativo-llm-vs-rag`.
Base revisada: `991209019eea829bd3dc9d0c19be93211f0f38b8`.
As correções permanecem no working tree, sem commit, push ou merge.

## Correções e evidências

| Problema | Correção | Regressão automatizada |
| --- | --- | --- |
| Dose ambígua apagava filtro | Denominadores/composições completos; conflito ou ambiguidade abstém | 999 mg/5 mL, 999 + 888 mg, unidade desconhecida, texto versus seleção, composições válidas |
| Receita legítima excedia limite agregado | Inspeção por campo, incluindo posologia e pergunta; emergência prioritária | 50 itens válidos e ataque no último item |
| Simulação apresentada como LLM | Remoção do gerador com erros programados; fixture mínima em evals | Smoke explícito v1/v2 não aprova entrega científica |
| Fallback ocultava erro | Erro explícito e metadados em cada geração | Timeout, HTTP 429, JSON inválido, schema inválido e resposta vazia nos dois clientes |
| Provedor inferido por chamada extra | Exatamente duas gerações por caso; par inválido excluído dos dois braços | Contagem de chamadas, modelo incompatível, latência e erro preservados |
| Citação validava apenas ID | Todas as citações exigem chunk recuperado, título e página exatos | Página/título inventados, ID desconhecido, citação parcial e mistura válida/inválida |
| Heurística apresentada como RAGAS | Nomes explícitos, gabarito fora do contexto, factualidade desconhecida | Gabarito alterado não modifica overlap; afirmação absurda não vira verdade certificada |
| Aprovação fixa | Gates dinâmicos do ADR 0003; ausência não aprova | 0,85 reprovado, 0,92 aprovado, null não avaliado, NaN/infinito rejeitados |
| Benchmark avaliava só primeiro medicamento | audit_items transcritos da pergunta; todos os cartões conferidos | Datasets validados e benchmarks v1/v2 |

## Validação executada

| Comando / escopo | Resultado |
| --- | --- |
| `cd backend; uv run pytest -q --show-capture=no` | 114 passaram |
| `uv run ruff check . ../evals ../observability` (backend) | Sem erros |
| `uv run ruff format --check . ../evals ../observability` (backend) | 84 arquivos conformes |
| `uv run mypy app tests ../evals/runners ../evals/baselines ../observability` (backend) | 82 arquivos sem erros |
| Mypy estrito dos runners/baselines, na raiz com MYPYPATH=backend | 9 arquivos sem erros |
| `uv tool run bandit -r backend/app evals -ll` | Zero achados; 5.599 linhas analisadas |
| `validar_datasets.py` | Quatro datasets válidos |
| `ragas_runner.py --dataset ...golden_set_v1.jsonl` | 16 casos; Hit@3/Recall@3/roteamento/bloqueio/abstenção 100%; MRR 1 |
| `ragas_runner.py --dataset ...golden_set_v2_consolidado.jsonl` | 22 casos; mesmas métricas 100%; MRR 1 |
| Guardrail clínico com recall mínimo 1 e falso bloqueio máximo 0,05 | Recall 100%; falso bloqueio 0% |
| Anti-injeção com recall mínimo 1 e falso bloqueio máximo 0 | Recall 100%; falso bloqueio 0% |
| `comparar_semana3.py --synthetic-smoke` | 22 pares sintéticos; zero pares inválidos; RAGAS não avaliado |
| `git diff --check` | Sem erros |

A CI de qualidade agora inclui evals e observability. O smoke é explícito no Makefile
 e no workflow. Os pacotes do backend e o corpus não ganharam dependências nem foram
regerados. As perguntas/gabaritos dos Golden Sets não mudaram; apenas o payload HTTP
estruturado foi acrescentado e é validado como transcrição da pergunta.

## Limites

Esses resultados valem para os casos executados. Não certificam ausência universal
de bugs, segurança em entradas inéditas ou desempenho de LLMs. Não houve execução
externa de Gemini/Ollama, avaliação RAGAS ou revisão factual humana. Docker não estava
disponível no ambiente local; o build/smoke continua no workflow. Checks remotos não
foram executados por esta revisão. A entrega científica permanece pendente conforme
[documentação](../entregaveis_semana3_comparativo.md) e [ADR 0004](../adr/0004_integridade_comparativo_semana3.md).
