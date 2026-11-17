# ADR 0006 — Correspondência documental e contrato de evidências

- Data: 2026-11-17.
- Status: implementado na branch; revisão do squad pendente antes do merge.
- Complementa ADRs 0004 e 0005; não altera metas de avaliação.

## Contexto

A revisão da portação pré-Semana 4 encontrou perda do vínculo ingrediente/dose, remoção de detalhes contraditórios da consulta, falsos bloqueios administrativos e aliases sem lastro suficiente. O carregamento das evidências era descrito como integração ao RAG, embora não houvesse consumidor de resposta.

## Decisão

1. Confirmar associações intercaladas por pares ingrediente–concentração contra uma apresentação canônica. Ordem diferente dos pares é aceitável; doses trocadas, ingredientes repetidos/extras/ausentes exigem abstenção. `doses_no_texto` lança `ValueError` para associação intercalada não confirmada; o caso de uso converte isso em abstenção sem fallback normativo.
2. Aceitar omissão de sufixo documental no filtro de concentração, mas exigir correspondência exata quando explicitado. Não calcular equivalências químicas nem apagar percentual, volume ou dispositivo divergente.
3. Aplicar equivalências previamente escopadas ao candidato real do catálogo, não à presença textual de todos os seus sais. Isso permite sacubitril/valsartana abreviado sem estender a equivalência a outros medicamentos.
4. Preservar formas literais de F04 quando uma fusão acrescentaria informação não confirmada. Adiar aliases de insulina humana genérica para NPH, beclometasona sem denominador para mcg/dose e budesonida 32 mcg/dose para 32 mcg. A quantidade de registros é resultado, não meta de aprovação.
5. Remover somente gatilhos administrativos locais do guardrail. Menção a SUS, procuração ou notificação não libera a cláusula inteira. Pedidos clínicos vizinhos, emergência e anti-injection mantêm suas verificações.
6. Disponibilizar `EvidenceRepositoryPort` e `EvidenceChunkDTO` na aplicação. Vínculo com catálogo por `occurrence_ids`; preservar URL, versão, página, hash e texto literal. IDs duplicados e vínculos solicitados inexistentes falham explicitamente. O startup valida cobertura do catálogo pelo pacote de evidências.
7. O repositório está preparado para agentes, mas não é entrada do ranking lexical nem fonte das respostas atuais. O RAG continua usando 20 normativos. Evidência de presença não comprova elegibilidade, validade de receita ou estoque atual. A ativação do consumidor pertence à integração futura, com teste ponta a ponta.

## Consequências e validação

- Regressões HTTP cobrem doses trocadas, ordem válida, conflito estruturado, percentual, embalagem e equivalência escopada. Teste de três componentes usa fixture declaradamente sintética apenas em `tests/`.
- Corpus regenerado em diretório separado; comparação byte a byte de catálogo, normativos e evidências e igualdade do manifesto exceto timestamp.
- Regras e ocorrências de apoio: `data/manifests/canonical_reconciliation_rules.json`. Snapshot CEAF: `data/manifests/ceaf_snapshot_source.json`.
- IDs sequenciais `MED-CONS-*` podem mudar após reconciliação. Não persistir esses IDs entre versões sem hash do corpus; `occurrence_ids` são o vínculo estável de proveniência.
- Revisão de domínio do squad e CI no commit final continuam necessárias. Testes determinísticos não aprovam agentes ou geração por LLM.

## Reversão

Após commit/merge, reverter o commit/PR da portação como unidade (código, testes, derivados e manifesto). Antes do commit, preservar diff e arquivos novos antes de reversão seletiva. Trocar para `main` não reverte alterações locais. Reverter só a correção reintroduz os defeitos documentados e não é recomendado.
