# Validação da preparação para quinta-feira

Branch: `feat/semana3-comparativo-llm-vs-rag`. Base da revisão: `bbe142c`.
Nenhum merge realizado. Resultados científicos do modelo local continuam pendentes.

## Correções

- API rejeita composições com doses parcialmente reconhecidas. Quantidade explícita
  de embalagem e o qualificativo “diabetes tipo 1/2” não viram doses desconhecidas.
- Respostas truncadas do Ollama invalidam a geração, preservando texto parcial e
  consumo informado pelo provedor.
- Checkpoint atômico por braço, identidade por código/dataset/corpus/modelo e
  retomada sem regenerar respostas já registradas.
- Auditoria humana vinculada à coleta e respostas, com IDs únicos, revisor,
  evidências, contagens inteiras e denominadores nulos quando não há afirmações.
- Auditoria cobre todas as respostas; agregados de controles e LLM ficam separados.
- Avaliação com event loop persistente, caches por métrica/par, histórico de
  tentativas e registro das respostas HTTP do juiz.
- Consolidação offline preserva escores e versões de relatório/auditoria.
- CI instala o ambiente isolado e exercita quatro métricas oficiais com HTTP simulado.
- Roteiro de execução substitui estimativas de hardware não medidas por piloto real.

## Evidências locais

| Checagem | Resultado |
| --- | --- |
| Backend pytest | 142 testes aprovados |
| Ambiente isolado evals | 1 teste de integração aprovado: quatro métricas oficiais, dois casos, cache e JSON inválido do juiz |
| Ruff lint e formatação | Aprovados; 94 arquivos formatados |
| Mypy | Aprovado em 91 arquivos |
| Datasets | Validação estrutural aprovada |
| Benchmark v1 (16 casos) | Indicadores publicados pelo runner em 100%; MRR 1 |
| Benchmark v2 (22 casos) | Indicadores publicados pelo runner em 100%; MRR 1 |
| Guardrail | Recall de bloqueio 100%; falso bloqueio 0% no conjunto testado |
| Smoke sintético + retomada | Concluídos; zero pares inválidos; sem métricas científicas fabricadas |
| Lockfiles backend/evals | Sem alteração |
| git diff --check | Aprovado |

Uma regressão intermediária do parser em GOLD-010 foi detectada pelos benchmarks,
corrigida e coberta por teste. Os números acima são da execução posterior à correção.

## Limites da validação

Não houve inferência real do Qwen neste computador: Ollama não estava instalado.
O teste isolado usa a biblioteca oficial, mas respostas HTTP simuladas; não mede
qualidade de LLM. Docker não estava disponível localmente; o workflow mantém o
build e a verificação do corpus na imagem para a CI.

Os gabaritos históricos não foram reescritos para aumentar métricas. A
[curadoria técnica](curadoria_semana3.md) explicita ambiguidades e pontos que
exigem consulta normativa na revisão humana, especialmente GOLD-017/018/020.
Isso impede declarar a entrega científica pronta apenas com testes de software.

## Execução presencial

Seguir [o roteiro do MacBook](plano_execucao_semana3_local_macbook.md): preparação,
`make semana3-pilot`, `make semana3-run`, revisão humana e `make semana3-finalize`.
Conferir o status científico no relatório; aprovação de metas não é presumida.
Levar todas as alterações desta branch ao Mac antes de executar.
