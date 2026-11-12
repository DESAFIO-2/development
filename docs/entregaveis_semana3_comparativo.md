# Semana 3 — protocolo de comparação e situação da entrega

**Situação em 12/11/2026: coleta real e RAGAS oficial concluídos. Revisão factual humana pendente.**

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
| Comparação de respostas de modelo real | Desempenho observado de um modelo configurado | 22 casos coletados no MacBook M4, com 18 pares de LLM e quatro casos de controle |
| Faithfulness / Answer Relevancy / Context Recall / Context Precision RAGAS | Avaliação da geração por protocolo RAGAS | 18 pares avaliados sem erro. Duas das quatro metas do ADR 0003 atingidas |
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
- Na etapa de coleta, taxa de alucinação e métricas RAGAS ficam `null` / `NAO_AVALIADO`. O ADR 0003 mantém
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

## Execução local de 12/11/2026

A execução usou a revisão `b24fceb`, o Golden Set v2 de desenvolvimento, o
corpus v5 e `semana3-qwen14` (Qwen 2.5 14B Instruct Q4_K_M) no Ollama 0.32.0.
O piloto de dois casos, com BGE-M3 e RAGAS 0.4.3, concluiu a inferência em
6 min 38 s. Os seus escores ficam no relatório do piloto.

O run `db9e9c3e933d46e7ae9f617743314f78` registrou 22 pares, sem falhas de
provedor ou pares inválidos. Os quatro casos de controle são duas consultas
de abstenção e dois bloqueios clínicos. Os agregados abaixo usam os 18 casos
positivos com dois braços gerados pelo modelo.

O RAGAS calculou os 90 escores dos 18 pares na primeira tentativa. A coleta
completa e a avaliação levaram 1 h 3 min 58 s. Consolidação
`ragas_v1/consolidacoes/a49634ca9c484123bcefe5df6949e90c`.

| Métrica oficial | Sem RAG | Com RAG | Meta ADR 0003 | Resultado |
| --- | ---: | ---: | ---: | --- |
| Faithfulness | Não aplicável | 0,8698 | 0,92 | Reprovado |
| Answer Relevancy | 0,3239 | 0,6751 | 0,88 | Reprovado |
| Context Recall | Não aplicável | 0,9491 | 0,90 | Aprovado |
| Context Precision | Não aplicável | 1,0000 | 0,88 | Aprovado |

O braço com RAG teve Answer Relevancy maior nos 18 pares, com diferença
média de 0,3512 na escala de 0 a 1. Os resultados descrevem o conjunto de
desenvolvimento sob julgamento do mesmo modelo que gerou as respostas.

Sete casos sem RAG (`GOLD-002`, `GOLD-007`, `GOLD-010`, `GOLD-017`, `GOLD-018`,
`GOLD-019` e `GOLD-021`) receberam Answer Relevancy 0,0000. Nesses casos o modelo
respondeu de forma genérica ou declarou não poder confirmar a informação, e o juiz
marcou a resposta como evasiva (`noncommittal = 1`), o que zera a métrica no
RAGAS 0.4.3. Os registros do juiz estão no pacote de evidências. Não houve falha
de execução nesses pares.

| Diagnóstico | Sem RAG | Com RAG |
| --- | ---: | ---: |
| Rota detectada pela heurística coincide com o rótulo | 7/18 | 18/18 |
| Latência mediana da geração | 10,62 s | 22,06 s |
| Respostas com todas as citações válidas | Não aplicável | 1/18 |

O ganho de 11 casos na heurística de rota equivale a 61,1 pontos percentuais
neste conjunto. Cinco respostas com RAG omitiram a citação no formato pedido.
Doze incluíram citações que falharam na validação, por exemplo a troca de
`nº` por `no`, título abreviado ou duas fontes agrupadas no mesmo colchete.
A conferência de metadados tem escopo distinto da revisão das afirmações.

Na inspeção dos textos e dos trechos recuperados, três casos merecem revisão:

- `GOLD-018` atribui ao Dignidade Menstrual a opção de retirada por procuração
  e omite a autorização que consta de `expected_documents`. O trecho recuperado
  reúne regras para públicos e itens distintos.
- `GOLD-020` combina o trecho sobre aplicação de injetáveis na UBS com o trecho
  sobre receita de controle especial. O contexto descreve os requisitos em
  frases separadas, e o caso também deixa a apresentação em aberto.
- `GOLD-022` passa na validação do trio de metadados, mas atribui ao médico a
  assinatura da Declaração Autorizadora. O trecho citado atribui ao médico a
  assinatura do LME. A resposta também deixa de informar os campos do LME
  pedidos na pergunta.

Validação local com os ambientes travados. Passaram 142 testes do backend,
um teste de transporte do RAGAS, Ruff, Mypy, os dois benchmarks determinísticos
e o smoke sintético. O Docker serviu health, autocomplete e auditoria via
HTTP. O corpus foi regenerado em uma pasta temporária com os mesmos arquivos
derivados e hashes.

A precisão por IDs dos chunks retornados foi 55,00% micro (22/40) e
59,26% macro nos 18 casos positivos. Com três posições fixas por consulta,
Precision@3 foi 40,74% (22/54). O recall macro por IDs foi 100%. Essas medidas
usam os rótulos congelados do Golden Set.

Consulte o [relatório oficial por caso](resultados/semana3-2026-11-12/avaliacao_ragas.md)
e baixe o [pacote de evidências](resultados/semana3-2026-11-12/semana3-evidencias.zip).
O pacote inclui o dataset, as respostas, os manifests, os registros do juiz,
os checkpoints e a ficha de auditoria factual humana pendente. Extraia o ZIP,
entre na pasta `semana3-evidencias` e rode `python3 verificar.py` com Python 3.12+
para conferir os hashes e recalcular as médias e a precisão por IDs sem inferência.
