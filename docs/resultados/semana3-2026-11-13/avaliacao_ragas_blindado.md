# Avaliação Oficial RAGAS e Auditoria Factual — Semana 3

- **Status do entregável:** `RAGAS_CONCLUIDO_PENDENTE_AUDITORIA_FACTUAL`
- **Tipo de execução:** `COLETA_REAL`
- **Avaliador RAGAS (`ragas==0.4.3`):** `semana3-qwen14` (embeddings: `bge-m3`)
- **Erros do avaliador:** `0`
- **Aprovação critérios ADR 0003:** `False`

## 1. Métricas Oficiais RAGAS (Casos Positivos `PAR_LLM`)

> `Faithfulness`, `Context Recall` e `Context Precision` exigem contexto recuperado e são registrados como `NAO_APLICAVEL` no braço sem RAG.

| Métrica RAGAS | Braço A (Sem RAG) | Braço B (Com RAG) | Meta ADR 0003 | Status Gate |
| --- | ---: | ---: | ---: | --- |
| `faithfulness` | NAO_APLICAVEL | 0.8698412698412699 | 0.92 | REPROVADO |
| `answer_relevancy` | 0.2907357930929105 | 0.6750542964389853 | 0.88 | REPROVADO |
| `context_recall` | NAO_APLICAVEL | 0.949074074074074 | 0.9 | APROVADO |
| `context_precision` | NAO_APLICAVEL | 0.9999999999416667 | 0.88 | APROVADO |

## 2. Verificação Factual Independente (Denominadores Explícitos)

Auditoria factual humana **NAO CONCLUIDA**. Preencha `auditoria_factual_humana.json` no diretório da coleta. Execute --consolidate-only para consolidar sem novas chamadas ao juiz.

## Diferenças pareadas de Answer Relevancy

| Caso | Sem RAG | Com RAG | Diferença (com − sem) |
| --- | ---: | ---: | ---: |
| GOLD-001 | 0.5041 | 0.8258 | 0.3217 |
| GOLD-002 | 0.0000 | 0.6987 | 0.6987 |
| GOLD-003 | 0.2940 | 0.4811 | 0.1871 |
| GOLD-004 | 0.5021 | 0.5777 | 0.0756 |
| GOLD-005 | 0.6225 | 0.7420 | 0.1195 |
| GOLD-006 | 0.4527 | 0.5481 | 0.0954 |
| GOLD-007 | 0.0000 | 0.8175 | 0.8175 |
| GOLD-008 | 0.5646 | 0.6494 | 0.0848 |
| GOLD-009 | 0.5610 | 0.7220 | 0.1611 |
| GOLD-010 | 0.0000 | 0.8245 | 0.8245 |
| GOLD-011 | 0.6111 | 0.8398 | 0.2287 |
| GOLD-012 | 0.5533 | 0.6705 | 0.1172 |
| GOLD-017 | 0.0000 | 0.5900 | 0.5900 |
| GOLD-018 | 0.0000 | 0.6528 | 0.6528 |
| GOLD-019 | 0.0000 | 0.6393 | 0.6393 |
| GOLD-020 | 0.5680 | 0.6796 | 0.1116 |
| GOLD-021 | 0.0000 | 0.4922 | 0.4922 |
| GOLD-022 | 0.0000 | 0.7000 | 0.7000 |

Limitações: desenvolvimento/regressão, sem teste independente de generalização. Gerador e juiz iguais podem compartilhar vieses. Revisão identificada, não cega. Faithfulness não comprova verdade factual nem garante ausência de alucinações.
