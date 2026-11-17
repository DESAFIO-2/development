# Portação curada pré-Semana 4 — registro após revisão

Atualizado em 17/11/2026. Segue o [runbook](../runbooks/portacoes.md), o [ADR 0004](../adr/0004_integridade_comparativo_semana3.md) e o [ADR 0006](../adr/0006_correspondencia_documental_e_evidencias.md). O [relatório independente](revisao_portacao_curada_2026_11_17.md) preserva os achados do estado anterior às correções.

## Origem, destino e preservação

| Campo | Revisão fixada |
| --- | --- |
| Destino | `https://github.com/DESAFIO-2/development.git`, base `57859c81370befdf70b87ede4006b106db3d1449` |
| Branch | `feat/pre-semana4-portacao-curada-de-ds` |
| Engenharia de Dados | `https://github.com/DESAFIO-2/data-engineering.git`, main `8d76f923354a4707810be38e238a8a3ea035554e` |
| Ciência de Dados | `https://github.com/DESAFIO-2/Data-Science.git`, main `d1f8fe1bf43b7c45e88d6b6907166845d0281601` |
| Última portação v9 | Incorporada à base; origem DE no mesmo SHA, conforme `corpus_v9_source.json` |

Referências remotas conferidas na revisão. Alterações locais e branch preservadas, sem merge, commit ou push. Não houve execução de scripts externos para importar automaticamente código ou dados novos.

## Decisão por artefato

| Artefato | Decisão e alcance |
| --- | --- |
| Estoque CEAF de DS | Importar snapshot sem alteração; conteúdo comparado com SHA fixado. Sem ativar consulta de estoque. |
| Normalização de sais e agrupamento F04 | Adaptar ao consolidado local; preservar ocorrência literal e característica de liberação. |
| Associação intercalada e concentração | Adaptar preservando pares ingrediente/dose e rejeitando detalhes conflitantes. |
| Guardrail clínico DE/DS | Adaptar com negativos administrativos e casos mistos, além dos 19 positivos clínicos. |
| Evidências v2 | Preparar repositório e Port, validar vínculos e incluir no Docker. Ainda não alimenta ranking/resposta. |
| Correção ortográfica | Método disponível e testado; sem consumidor HTTP ativo. |
| Diagnóstico DE v9→v10 | Referenciar; candidatos de deduplicação não são aprovação humana de toda fusão. |
| Pré-exames DS e PDF gerado a partir de JSON | Rejeitar até lastro primário: levantamento F12 não sustenta preparos específicos. ReportLab não prova autoria por IA. |
| Avaliação sintética rotulada RAGAS, catálogo antigo, Chroma e Airflow externos | Não portar; manter protocolo e contratos do development. |
| Grafo, memória e voz | Adiar até estabilização do colega e portação própria por SHA. |

## Correções da revisão

- R1: pares ingrediente/dose confirmados; inversão legítima aceita, doses trocadas rejeitadas mesmo com seleção estruturada.
- R2: omissão de detalhe não autoriza contradição; percentual, volume e dispositivo explícitos precisam coincidir.
- R3: navegação SUS/Farmácia Popular, procuração e notificação passam, sem liberar pedidos clínicos adjacentes ou emergência.
- R4: beclometasona 50/250 mcg mantém apresentação literal F04. Não acrescentar `/dose` ou via oral/nasal sem confirmação. Retirados também aliases insulina humana genérica→NPH e budesonida 32 mcg/dose→32 mcg.
- R5: sacubitril/valsartana abreviado é confirmado contra candidato canônico; doses conflitantes e outros medicamentos continuam rejeitados.
- Evidências: Port e DTO na aplicação, URL preservada, duplicatas rejeitadas e ocorrência solicitada inexistente causa erro. Startup confirma cobertura do catálogo.

## Dados, hashes e identidade

- Catálogo: **1.708 apresentações**, IDs únicos, **2.087 ocorrências** preservadas 1:1, sem itens sem ocorrência.
- Rotas: 870 UBS, 478 CEAF, 318 hospitalares e **42 Farmácia Popular**. A rota prioritária NPH já existia na base; mantê-la e preservar separadamente a ocorrência genérica F04 não produz relação 1:1 entre 41 linhas F04 e registros canônicos. Não forçar essa contagem para aprovar dados.
- Normativos: 20. Evidências: 2.114, cobrindo todas as ocorrências do catálogo.
- `manifest.json` preserva schema `2026.4.0` e registra novos hashes. Identificar esta variante pelo hash, não apenas pela versão textual.
- `canonical_reconciliation_rules.json` lista aliases herdados/adaptados e occurrence IDs de apoio. Não amplia aprovação humana anterior; revisão do squad precede merge.
- `ceaf_snapshot_source.json` fixa SHA da origem, SHA-256 local e **857 registros, 290 códigos, 294 descrições**, com datas por registro de 05/11 e 16/11. Timestamp geral não garante frescor individual.
- `output/revisao-portacao-2026-11-17/reconciliacao_por_ocorrencia.json` registra diferenças por ocorrência contra a base, inclusive mudanças de IDs sequenciais. Não persistir `MED-CONS-*` entre versões sem hash do corpus.

## Validação no consumidor

Ambientes locais `.venv` existentes; `uv` indisponível no PATH local. Na imagem Docker, o build executa `uv sync --locked --no-dev --no-install-project`.

| Checagem | Resultado após correções |
| --- | --- |
| `cd backend && .venv/bin/python -m pytest -q` | 317 passed |
| Ruff check / format --check | Sem erros; 102 arquivos formatados |
| Mypy app/tests/evals/observability | Sem erros em 99 arquivos |
| `evals/.venv/bin/python -m pytest evals/tests -q` | 1 passed |
| `validar_datasets.py` | 5 datasets íntegros |
| Guardrail clínico / anti-injection | Recall 100%, falso bloqueio 0% nos respectivos datasets |
| Golden v1/v2 | Gates determinísticos preservados, 16/22 casos |
| Comparativo `--synthetic-smoke` | 0 pares inválidos; RAGAS/factualidade NÃO AVALIADOS |
| Segurança `--synthetic-smoke --fail-on-api-elim` | API real C aprovada 4/4 em cada dimensão; A/B/D são fixtures |
| 10 reproduções da revisão | Comportamento esperado em `resultados_apos_correcao.json` |
| Regeneração isolada | Catálogo/normativos/evidências idênticos byte a byte; manifesto igual exceto timestamp |
| Docker build | Passou, imagem local `sus-cidadao-backend:portacao-review` |
| Docker smoke HTTP | Passou: startup, health, autocomplete e 7 auditorias em container temporário sem portas publicadas |

Os resultados anteriores em `resultados.json` foram preservados. Smokes corrigidos em `/private/tmp/portacao-corrigida-smoke` e `/private/tmp/portacao-corrigida-security`. Não foi feita avaliação nova com LLM real.

## Contrato para os agentes

- Injetar Ports existentes, inclusive `EvidenceRepositoryPort`; não reimplementar segurança em prompts.
- Juntar evidências por `CanonicalMedicationItem.occurrence_ids`. `medicine_id` da origem (`med-*`) e ID canônico (`MED-*`) são namespaces distintos.
- Evidências comprovam presença documental; normativos sustentam instruções administrativas. Não misturar indiscriminadamente 2.114 evidências ao ranking das 20 normas.
- API segue determinística. `pergunta_adicional` é inspecionada, mas não respondida via RAG; `tipo_prescritor` é inspecionado, mas não decide elegibilidade. Exigem contrato e validação próprios na Semana 4.
- Desambiguação progressiva, persistência/isolamento de sessões, estoque e geração acolhedora continuam adiados. Antes de ativar geração: validar saída, citações e falhas de provedor; fallback de produção explícito, nunca silencioso em avaliação.
- Curadoria de `CHK-COMP-PFPB-003` e `CHK-PFPB-001` continua pendente conforme portação v9. Não declarar aprovação documental integral ou qualidade dos agentes por estes testes.

## Ativação e reversão

Ativação em `main` somente após CI no commit final, smoke Docker e revisão do squad conforme CONTRIBUTING/CODEOWNERS. A portação permanece nesta branch.

Não usar `git checkout main` como reversão. Antes de qualquer descarte local, salvar patch e cópia dos arquivos novos. Após commit/merge, reverter o commit/PR real da portação como unidade: código, testes, dados e manifestos. A base `57859c81370befdf70b87ede4006b106db3d1449` permite comparação/reconstrução, restaurando também limitações anteriores. Nenhuma reversão foi executada.
