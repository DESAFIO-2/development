# Portação entre branches e repositórios

Este procedimento vale para contribuições vindas de qualquer branch ou repositório, inclusive Engenharia de Dados e Ciência de Dados. A portação deve ter origem verificável, escopo explícito, validação no consumidor e um caminho de reversão.

## 1. Fixar origem e destino

- Conferir `git status --short --branch`, remotes e SHA do destino. Preservar alterações locais e trabalhar na branch pedida. Uma atualização de origem não autoriza merge em `main`, push, rebase, reset ou troca de branch.
- Identificar URL, branch ou tag e SHA imutável da origem. Um clone existente pode estar desatualizado. Conferir a referência remota e obter o SHA em um checkout isolado quando houver diferença. Preservar o checkout de origem. Se o remoto estiver inacessível, registrar a última revisão verificável e deixar explícito o que depende da revisão mais nova.
- Comparar a origem com o SHA da última portação. Na primeira portação, documentar a base escolhida. Quando os repositórios têm históricos distintos, comparar primeiro o intervalo de commits na origem e depois os contratos e arquivos equivalentes no destino.
- Ler o diff, os manifestos, as notas do release e os testes associados antes de executar código externo. Verificar se a revisão é rascunho, candidata ou aprovada e para qual escopo.

## 2. Decidir por artefato

| Decisão | Quando aplicar |
| --- | --- |
| Importar | Dados ou código revisado, com licença/permissão de redistribuição e contrato compatível. Preservar a origem e registrar o SHA. |
| Adaptar | O conteúdo é útil, mas usa schemas, IDs, dependências, arquitetura ou ambiente diferentes. Reusar interfaces do destino e cobrir a transformação com testes. |
| Referenciar | Relatórios, scripts de curadoria, experimentos e artefatos intermediários úteis para auditoria. Vincular à revisão de origem. |
| Adiar | Mudança depende de validação, revisão, credencial, infraestrutura ou decisão de produto. Registrar a condição para incorporar. |

- Preferir a menor unidade coerente. Em branches de histórico comum, usar `cherry-pick -x` quando o commit inteiro for adequado. Em repositórios separados, aplicar alterações selecionadas ou gerar os derivados localmente. Um merge de históricos só cabe quando a intenção for de fato integrar os históricos.
- Mapear consumidores, contratos HTTP e de dados, flags, dependências, CI, Docker e efeitos de reexecução. Separar mudanças de dados, migrações e integrações opcionais para facilitar revisão e reversão.
- Revisar arquivos selecionados para evitar incorporar credenciais, dados pessoais, caches, índices locais, resultados experimentais obsoletos e binários sem origem e licença verificáveis. Usar datasets sintéticos ou públicos nas avaliações do projeto.

## 3. Portar dados e experimentos com rastreabilidade

- Fixar versão, SHA do commit, caminhos, schema, hashes e escopo de aprovação. Verificar bytes, contagens, tipos, chaves, unicidade, integridade referencial, proveniência por registro e exclusões. Registrar diferenças por ID estável e amostrar os casos de maior impacto.
- Preservar evidência literal separada de texto normalizado. Manter links entre ocorrência, entidade, fonte, página e chunk. Documentar mudanças de identidade e campos descartados. Uma versão nova pode manter a contagem e ainda alterar o significado de registros.
- Gerar catálogo, chunks e índices a partir da entrada versionada em diretório separado. Validar o conjunto antes de promovê-lo de forma consistente. Fixar versão e parâmetros do gerador e verificar a reprodutibilidade, descontando campos explicitamente voláteis. Manter a versão anterior disponível.
- Para modelos e métricas, preservar splits, IDs, hashes, prompts, modelo/versão, parâmetros e denominadores. Separar métricas de recuperação das métricas de aplicação e geração. Entradas de teste não devem receber campos do gabarito. Dados de treino, revisão, regressão e teste devem ter papéis explícitos.

## 4. Validar e preparar a entrega

1. Registrar a linha de base no destino antes da portação, inclusive falhas já conhecidas. Comparar com a candidata usando os mesmos casos, comandos e ambiente.
2. Executar formatação, lint, tipos, testes, integrações e smoke do consumidor real conforme o escopo. Para corpus do SUS Cidadão, verificar startup, autocomplete, auditoria, bloqueio clínico, abstenção, citações, Docker e os Golden Sets v1/v2. Explicar alterações esperadas e investigar regressões.
3. Conferir que o diff final contém apenas mudanças intencionais. Revisar mudanças de schema e dependências com os responsáveis definidos no `.github/CODEOWNERS`. Se alguma validação ficar bloqueada, registrar evidência, impacto e condição para concluir. Um teste informativo ou rascunho não satisfaz um critério obrigatório.
4. Manter a entrega na branch de destino. Quando for publicado um PR, anexar o registro de portação, resultados, incompatibilidades e estratégia de reversão. A promoção para `main` segue o fluxo de revisão e CI do projeto.

## Registro mínimo para a próxima portação

```text
Objetivo e branch/SHA de destino
URL, branch, SHA da origem e SHA da última portação
Artefatos e decisão por item (importar, adaptar, referenciar ou adiar)
Versão de schema, manifesto, hashes, aprovações e limitações
Mudanças de contrato e consumidores afetados
Comandos, resultados antes/depois, falhas conhecidas e evidências
Critério de ativação, versão anterior e procedimento de reversão
```
