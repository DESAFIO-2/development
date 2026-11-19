# Protocolo de Holdout Cego do Guardrail Clínico

O protocolo único e vigente está em
[`evals/configs/protocolo_holdout_guardrail.md`](../../evals/configs/protocolo_holdout_guardrail.md).
É ele que o `make guardrail-holdout` segue (arquivo `evals/datasets/holdout_guardrail_v1.jsonl`,
mínimo de 40 casos `bloquear` e 40 `permitir`, medição das camadas 1, 2 e combinada).

Este arquivo existia com uma versão anterior (30 casos, arquivo `guardrail_holdout_cego_v1.jsonl`).
As duas versões conviveram na `main` entre 17/11 e 19/11/2026. As regras que só existiam aqui
foram levadas para o protocolo vigente:

- rascunho fora de `evals/datasets/` até o congelamento, porque o validador do CI lê todos os
  `.jsonl` dessa pasta;
- SHA-256 do arquivo registrado junto com o hash do commit, antes da primeira medição;
- limite de falso bloqueio de 5% (`--max-falso-bloqueio 0.05`), além do recall de 100%.

Contexto de integridade: [ADR 0004](../adr/0004_integridade_comparativo_semana3.md) e
[ADR 0005](../adr/0005_escopo_clinico_e_inspecao_pdf.md).
