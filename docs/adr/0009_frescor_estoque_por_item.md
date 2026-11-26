# ADR 0009 — Frescor de estoque por item e atualização revisada

- Data: 2026-11-26.
- Status: implementado e validado localmente, inclusive Docker; execução operacional no GitHub pendente.

## Problema

O snapshot CEAF mistura datas de posição distintas. A data máxima do painel não
comprova atualização de todos os medicamentos. Uma data nula decodificada não
pode herdar a data da linha anterior. Coleta recente não atualiza a posição.

## Decisão

- Preservar `ultima_atualizacao` literal e converter sua data para UTC por item.
  Datas brasileiras sem fuso usam America/Sao_Paulo; datas ISO com fuso o preservam.
- Expor `updated_at` e `stale_warning` em cada item. Alertar para mais de 48 horas,
  data ausente/inválida ou futura; nunca substituir por data de coleta ou do painel.
- O resumo cobre todos os resultados filtrados, não apenas a página retornada:
  menor data conhecida se todas existem; nulo se alguma falta ou não há resultados.
  Alerta verdadeiro se algum item exige alerta ou se não há resultados.
- Manter `synced_at_utc` separado. O cabeçalho `panel_updated_at_utc` é metadado
  da última atualização observada, sem garantia de frescor dos itens.
- Atualizar snapshots por PR, serializando execuções. Coleta igual à proposta
  preserva o commit/revisão; retorno à base fecha proposta obsoleta. Publicação
  usa lease com SHA explícito para recusar sobrescrita de alteração concorrente.
- Snapshot continua embutido na imagem: merge deve ser seguido de rebuild/redeploy.
  Não ampliar cobertura UBS nem afirmar estoque em tempo real.

## Validação e reversão

Testes cobrem datas heterogêneas, nulos DSR, fonte antiga com coleta recente,
limite de página, datas futuras e transições A→B→A/A→B→B/A→B→C do PR.
A aprovação científica da geração permanece independente e pendente.

Após commit, reverter o commit real desta correção como unidade (backend, contratos,
workflow e documentação). Isso reintroduz risco de frescor incorreto; desabilitar a
exibição de disponibilidade até restaurar a correção. Não reverter dados da fonte
para fazê-los parecer atualizados.
