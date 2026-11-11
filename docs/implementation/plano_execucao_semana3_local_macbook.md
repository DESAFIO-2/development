# Semana 3 — execução local no MacBook Air M4 (24 GB)

Estado: infraestrutura preparada; resultados reais e revisão humana ainda pendentes.
Trabalhar na branch `feat/semana3-comparativo-llm-vs-rag`, sem merge automático.
Os 22 casos são desenvolvimento/regressão; não constituem teste independente.

## 1. Preparar uma vez

Instalar Git, Python/uv, Make e Ollama nativo para macOS. O servidor de modelos
roda no host, fora do Docker. Usar a mesma revisão do código em toda a sessão.

```bash
git status --short --branch
make dev-install
make eval-setup
make test
make lint
make eval-test
ollama serve
```

Se o aplicativo Ollama já estiver ativo, não iniciar um segundo servidor.
Deixar o servidor em outro terminal. No terminal do projeto:

```bash
ollama pull qwen2.5:14b-instruct-q4_K_M
ollama pull bge-m3
ollama create semana3-qwen14 -f evals/ollama/Modelfile
```

`semana3-qwen14` fixa o modelo base Q4_K_M, contexto de 8192, temperatura 0 e
seed 42. A coleta também envia explicitamente contexto/seed. A avaliação utiliza
o mesmo alias via API compatível com OpenAI; os pesos são carregados localmente.
Os manifests registram versão do servidor, digest, tamanho e detalhes dos modelos.
Não atualizar modelos durante a execução. Não usar modelos cloud.

Não há benchmark medido deste MacBook: não prometemos tokens/s, tempo total nem
memória livre. Pesos, cache de contexto, embeddings, buffers e macOS compartilham
os 24 GB. Fechar aplicações pesadas e observar pressão de memória/Swap no Monitor
de Atividade. Usar energia externa e impedir suspensão durante a sessão.

## 2. Piloto real obrigatório (dois casos, fora da entrega)

```bash
make semana3-pilot
```

Executa coleta e quatro métricas oficiais, incluindo embeddings, em dois casos
consecutivos. Saída: `evals/reports/quinta_piloto/`. O status é
`PILOTO_NAO_E_ENTREGA`, mesmo se as métricas forem altas. O comando só termina
com sucesso operacional quando todas as métricas esperadas forem calculadas.
Anotar tempo, memória e qualquer truncamento/erro. Respostas do juiz e consumo
informado pelo provedor ficam em `ragas_v1/http/`; latências por métrica/par ficam
nos checkpoints. Se houver erro, resolver antes da coleta definitiva.

O piloto precisa exercitar inferência: se já existir uma execução concluída, o
comando retoma/reutiliza seu cache. Para novo piloto independente:

```bash
make semana3-pilot PILOT_DIR=evals/reports/quinta_piloto_02
```

## 3. Coletar e avaliar os 22 casos

```bash
make semana3-run
```

Pasta padrão: `evals/reports/quinta_coleta/`. Para outro experimento, informar
`RUN_DIR=evals/reports/nome_novo`. O wrapper executa as etapas em ambientes
separados e informa o status científico. Seu código 0 significa inferência
concluída; não significa entrega aprovada. A auditoria continuará pendente.

Antes de coletar, ler `docs/implementation/curadoria_semana3.md`. O dataset v2 é
preservado para regressão. Suas limitações de apresentação/referência são
publicadas e devem ser consideradas na revisão factual; não tratar o gabarito
como fonte normativa independente. Nenhum caso pode ser eliminado depois de ver
as respostas. Uma alteração futura exige nova versão do dataset e nova coleta.

## 4. Interrupção, falhas e retomada

Repetir `make semana3-run` na mesma pasta retoma chamadas faltantes e reutiliza
respostas recebidas, inclusive erros registrados. Nunca executar dois processos
na mesma pasta simultaneamente. Identidade incompatível (modelo, código, corpus,
dataset ou parâmetros) interrompe a retomada; criar outra pasta para outro protocolo.
Cada gravação usa arquivo temporário, fsync e substituição atômica.

Uma interrupção antes de receber/gravar uma resposta pode exigir repetir aquela
chamada em andamento; as respostas já gravadas são preservadas.
Falha de geração invalida o par e impede a certificação dessa coleta. Investigar
e preservar a execução; um novo experimento deve ser identificado como tal, sem
selecionar a melhor resposta entre execuções.

Para falhas do juiz, a coleta continua intacta. Tentativas adicionais são
explícitas, limitadas a três por par e preservam histórico. Métricas já concluídas
não são repetidas:

```bash
uv run --project evals python evals/runners/avaliar_ragas_oficial.py \
  --coleta-dir evals/reports/quinta_coleta \
  --evaluator-model semana3-qwen14 --embedding-model bge-m3 --retry-failed
```

O SDK tem retry HTTP desativado; retries de validação estruturada do Instructor
podem ocorrer internamente e suas respostas HTTP são registradas. Não escolher
o maior escore. Para reavaliar deliberadamente, usar `--evaluation-name ragas_v2`,
preservando `ragas_v1` e declarando por que o protocolo foi repetido.

## 5. Revisão humana e fechamento sem inferência

Preencher `quinta_coleta/auditoria_factual_humana.json` para todas as respostas,
incluindo abstenções e controles. Registrar revisor, observações e referências
com documento/página/seção e fato verificado. Conferir cada medicamento. Não
modificar textos, referências, IDs ou hashes. A ficha identifica os braços:
não declarar esta revisão como cega.

Contagens são inteiros não negativos. Quando não houver afirmações factuais,
manter zero e justificar; taxas com denominador zero ficam nulas. Contradição e
não verificabilidade são categorias distintas. Controles têm agregados separados.

```bash
make semana3-finalize
```

Pode desligar o Ollama antes desse comando: ele não instancia o juiz nem chama
modelos. Cada consolidação preserva uma versão com a auditoria usada em
`ragas_v1/consolidacoes/<id>/`. Os arquivos `avaliacao_ragas.json/md` na raiz da
coleta apontam para a última visão. Auditoria de outra coleta é rejeitada.

Códigos do avaliador: 0 = entrega concluída/metas aprovadas; 1 = avaliação
incompleta; 2 = entrega concluída/metas reprovadas; 3 = auditoria pendente ou piloto.
O Make mostra erro para códigos não zero: conferir o status, sem alterar metas.

## 6. Pacote a entregar

Preservar a pasta da coleta: dataset congelado, manifesto, checkpoints de geração,
respostas brutas, relatório de coleta, auditoria humana, manifesto da avaliação,
checkpoints/métricas/HTTP e consolidação escolhida em JSON/Markdown. O tracking
da etapa oficial é por artefatos JSON locais, não MLflow nativo. A etapa de coleta
mantém seu rastreador anterior, explicitamente separado.

Atualizar `docs/entregaveis_semana3_comparativo.md` com os resultados reais e os
identificadores escolhidos. Não substituir reprovações ou métricas ausentes.
Publicar denominadores, falhas, diferenças pareadas e limitações. Mesmo modelo
como gerador/juiz pode compartilhar vieses; revisão humana não é opcional.

## Referências de integração

- https://docs.ollama.com/api/tags (digests e quantização)
- https://docs.ollama.com/api/generate (consumo, conclusão e duração)
- https://docs.ollama.com/api/openai-compatibility (endpoint compatível)

Os testes de transporte da CI usam respostas HTTP simuladas com o RAGAS instalado.
Eles validam integração, não desempenho científico do modelo.
