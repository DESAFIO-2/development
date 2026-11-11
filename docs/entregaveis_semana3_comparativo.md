# Semana 3 — protocolo de comparação e situação da entrega

**Situação: implementação corrigida; experimento científico ainda não concluído.**

## Retificação dos resultados anteriores

Os números publicados em `9912090` (77,27% de alucinação sem RAG contra 0% com RAG,
Faithfulness 0,9754 etc.) foram produzidos por respostas programadas. Não são medidas
de Gemini, Ollama ou RAGAS e ficam retirados como evidência de superioridade.
Os relatórios locais antigos `comparativo_semana3_llm_vs_rag.*` também são obsoletos;
não devem ser enviados à banca nem combinados com o schema `comparativo-v2`.

| Evidência | O que demonstra | Situação |
| --- | --- | --- |
| Pytest, transporte HTTP mockado e fixture sintética | Contratos, tratamento de erros e encanamento | Automatizados em CI |
| Benchmark determinístico v1/v2 | Recuperação e roteamento nos casos rotulados | Avaliado separadamente |
| Comparação de respostas de modelo real | Desempenho observado de um modelo configurado | Pendente de execução real |
| Faithfulness / Answer Relevancy / Context Recall / Context Precision RAGAS | Avaliação da geração por protocolo RAGAS | Implementadas no estágio 2 oficial; execução real pendente |
| Taxa de alucinação factual | Julgamento de afirmações com evidências e rubrica | Não avaliada; revisão factual pendente |

## Protocolo implementado

- Mesmo provedor, modelo configurado, pergunta, instrução de sistema, temperatura zero
  e limite de 450 tokens nos dois braços. Apenas o contexto recuperado muda.
- O baseline sintético está em `evals/baselines/synthetic_generation.py`; retorna uma
  mensagem de fixture ou uma citação e não tenta imitar erros de uma LLM.
- Ausência de chave/modelo, timeout, HTTP inválido e resposta vazia não ativam fallback.
  O erro é registrado em `geracao.error_code`, o par recebe `FALHA_PROVEDOR` e **ambos**
  os braços são excluídos dos denominadores de pares válidos.
- Provedor, modelo, origem da execução, latência, texto e evidências são registrados
  por resposta. Não existe chamada extra para adivinhar o provedor do experimento.
- `CONTROLE_DETERMINISTICO` identifica guardrail/abstenção da aplicação, não desempenho
  intrínseco de uma LLM. `PAR_LLM` identifica pares com duas gerações reais sem erro.
- Metadados de todas as citações precisam coincidir com chunk, título e página recuperados.
  Isso não comprova que as afirmações do texto sejam verdadeiras.
- Overlap de tokens do contexto usa apenas os trechos efetivamente recuperados, sem
  acrescentar o gabarito. Overlap da pergunta é outra heurística lexical. Nenhum é RAGAS.
- Taxa de alucinação e métricas RAGAS ficam `null` / `NAO_AVALIADO`. O ADR 0003 mantém
  os mínimos 0,92 / 0,88 / 0,90 / 0,88; ausência de medida nunca resulta em aprovação.
- Cada execução gera JSON e Markdown em diretório único, com hashes normalizados LF
  do dataset, corpus e código do protocolo. A versão do schema é `comparativo-v2`.

## Execução

Na raiz do repositório:

```powershell
# Offline, sem chamada de modelo e sem conclusão científica:
uv run --project backend python evals/runners/comparar_semana3.py --synthetic-smoke

# Coleta real: configurar modelo explicitamente, sem valor padrão que possa ficar obsoleto.
$env:APP_LLM_PROVIDER = "gemini"
$env:APP_LLM_MODEL_NAME = "<modelo-disponivel-na-sua-conta>"
# Definir APP_GOOGLE_API_KEY no ambiente, sem versionar ou imprimir a chave.
uv run --project backend python evals/runners/comparar_semana3.py --provider gemini

# Alternativa local, com servidor Ollama já iniciado e modelo instalado:
$env:APP_LLM_MODEL_NAME = "<modelo-local-instalado>"
uv run --project backend python evals/runners/comparar_semana3.py --provider ollama
```

Os comandos usam variáveis do ambiente. Para `backend/.env`, execute a partir de
`backend` com o caminho `../evals/runners/comparar_semana3.py`.

Saídas: `evals/reports/smoke_sintetico_semana3_<id>/` ou
`evals/reports/coleta_real_semana3_<id>/`. Código de saída 0 significa etapa de coleta concluída (real ou sintética);
1 significa par inválido. Isso nunca certifica a entrega científica. A CI executa somente `make compare-smoke`.

## Correção dos fixtures de auditoria

As perguntas e gabaritos v1/v2 foram preservados. Foi acrescentado `audit_items` aos
casos com vários medicamentos para representar uma receita com itens separados,
como exige a API. Esses nomes são transcritos da pergunta, sem injetar campos do
gabarito. A pergunta original continua sendo usada integralmente na recuperação e
na comparação de geração. O benchmark agora verifica a rota de todos os cartões.
A alteração muda o hash do dataset; resultados históricos não devem ser tratados
como execução do mesmo fixture HTTP. As entradas ainda exigem curadoria do domínio,
especialmente quando a pergunta não especifica uma apresentação (por exemplo GOLD-020).

## Condições para o entregável científico

Congelar modelo acessível, corpus, dataset revisado e rubrica factual antes de coletar;
executar os dois braços sem substituir falhas; revisar afirmações e citações;
integrar um avaliador RAGAS validado e registrar sua versão/modelo/parâmetros;
publicar resultados observados e limitações, inclusive denominadores e falhas.
Nenhum resultado superior do RAG é pressuposto pelo protocolo.

A API de auditoria continua determinística; a geração de LLM está no experimento.
Chroma permanece adiado conforme o registro da portação. Não houve nova portação
nem alteração do corpus nesta correção.


## Execução local e fechamento

Roteiro atualizado: [execução no MacBook](implementation/plano_execucao_semana3_local_macbook.md).
Após preparar Ollama e o alias do Modelfile, executar `make semana3-pilot`,
`make semana3-run`, preencher a auditoria humana e executar `make semana3-finalize`.
A etapa 2 tem ambiente isolado `evals/` com RAGAS 0.4.3 e grava artefatos JSON locais.
Não chamar esse armazenamento de MLflow nativo.

A coleta tem retomada por braço, identidade por hashes e digest dos modelos.
A avaliação tem cache por métrica/par. Consolidação offline preserva escores e
versiona o relatório e a auditoria. Respostas não verificáveis não são
automaticamente falsas; suas contagens e taxas ficam separadas das contradições.
As métricas agregadas de LLM e de controles são identificadas separadamente.

Os 22 casos são desenvolvimento/regressão e têm limitações documentadas na
[curadoria](implementation/curadoria_semana3.md). O gerador e o juiz usam o mesmo
modelo; a revisão humana é identificada e não cega. Não se pode inferir
superioridade geral nem garantia de zero alucinação.

Resultados reais: **PENDENTES**. Não substituir esta indicação até executar o
modelo e concluir a revisão de todas as respostas. Metas reprovadas devem
permanecer publicadas; conclusão da entrega e aprovação das metas são distintas.
