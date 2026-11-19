# Revisão independente — fechamento da Semana 4 e triagem da portação v10

> Registro histórico anterior às correções. Consulte o [resultado da implementação](../implementation/correcoes_fechamento_semana4_2026_11_19.md) para o estado posterior.

Data: 19/11/2026. Esta revisão foi feita por agente de IA, com inspeção de código e execução de verificações; **não constitui revisão humana clínica**.

Destino: `development`, branch `main`, HEAD `3df4d8b7ccd243d8679f10d19cb08e8a84c8bda2`, **mais o diff local preexistente**, incluindo o runner/teste de avaliação ainda não versionados. Nenhuma alteração de aplicação, merge, troca de branch, commit ou push foi feita nesta revisão. Os arquivos acrescentados são este parecer e suas evidências.

Origem externa: `DESAFIO-2/data-engineering`, branch `feat/integracao-rag-v10`, SHA `2a9a521d8a06e5eb300f12f5b6547a0efd0f9869`, obtida em clone temporário isolado. Base da última portação: `8d76f923354a4707810be38e238a8a3ea035554e`. A comparação de origem abrange 151 arquivos alterados. Não houve importação de dados para o runtime.

As referências `arquivo:linha` abaixo correspondem ao estado local auditado, não apenas ao HEAD. O pacote [evidencias_semana4_2026_11_19](evidencias_semana4_2026_11_19/) preserva hashes do código, identidade da portação, logs e cópias dos relatórios experimentais examinados. Os relatórios originais em `evals/reports` são locais; sua existência não garante que acompanhem um checkout remoto.

## 1. Veredito executivo

**GO COM RESSALVAS para demonstrar e documentar a arquitetura da Semana 4. NO-GO para declarar fechamento integral dos critérios científicos ou “tudo validado”.** Antes do PR final, corrigir os gates de avaliação, isolar o teste que depende de Ollama, aplicar o limiar correto do holdout e alinhar os comandos de reprodução.

O fluxo determinístico funciona ponta a ponta: servidor FastAPI real passou em health, autocomplete, sete auditorias e dois grafos; a demonstração executou cinco cenários. A suíte passou em 436 testes com acesso ao Ollama local, mas um desses testes falha quando a rede está isolada. Essa condição impede interpretar “436 passed” como prova de uma CI autossuficiente.

Há evidência local preservada de inferência real de 7B e 14B: cinco casos por modelo, três gerações, uma abstenção e um bloqueio, sem falhas/rejeições na rodada v2. **Não refiz a coleta LLM nem o RAGAS nesta revisão.** Inspecionei respostas literais, metadados, manifestos e métricas existentes. Não há modelo que passe simultaneamente nos dois gates RAGAS medidos e no p95 de oito segundos. A avaliação automática não substitui a revisão factual exigida pelo ADR 0004.

**Recomendação de portação: encerrar a Semana 4 com o corpus v9 curado atual; abrir o primeiro PR da Semana 5 para adaptar v10.** A origem é rastreável e útil, mas não é uma substituição direta de arquivos: IDs de entidade, normalizações, receita de chunks e vínculos com o consumidor mudam.

## 2. Notas por dimensão

Notas são julgamento de engenharia desta revisão, não métricas de benchmark. Pesos somam 100%; funcionalidades das Semanas 5–7 não foram cobradas como entregas atuais.

| Dimensão | Nota | Peso | Justificativa verificável |
|---|---:|---:|---|
| Arquitetura e Clean Architecture | 8,2 | 15% | Casos de uso e Ports reaproveitados; `container.py` concentra composição. Grafo fora do domínio e gerador opcional. Há acoplamento concreto no container, aceitável nesse ponto de composição. |
| Multiagentes e colaboração | 8,0 | 15% | `orchestrator.py:67` configura barreira explícita; teste em `test_agents.py:241` usa rendezvous real entre trabalhadores e verifica isolamento. Não são quatro LLMs: três nós determinísticos e uma síntese opcional. |
| Motor determinístico, RAG e corpus | 8,0 | 15% | Golden v1/v2 passaram; 1.708 apresentações, 20 chunks normativos e 2.114 evidências no manifesto. Proveniência documental não equivale a estoque, elegibilidade individual ou confirmação clínica. |
| Segurança e LGPD | 7,3 | 15% | Inspeção granular, validação de saída e LangSmith desativado; regressões e smoke passaram. Holdout independente ainda não demonstrado e alvo Make não aplica o limiar prometido. |
| Qualidade de IA, avaliação e rigor científico | 5,5 | 15% | RAGAS oficial, distinção de mocks e ausência de revisão humana explícitas. Gates aceitam métricas ausentes; juiz apresenta falsos positivos comprovados; ambos os modelos falham em parte das metas. |
| Testes, CI/CD e engenharia | 7,0 | 10% | Ruff, mypy, Golden, evals e HTTP passaram. Um teste unitário depende de serviço externo; Docker e lock não foram revalidados nesta auditoria. |
| Mudanças do dia e documentação | 6,8 | 10% | Números publicados conferem com JSON local. Persistem comandos com diretórios divergentes, menção incorreta a `Send` e avaliação produzida por versão anterior do runner. |
| Prontidão para Semanas 5–7 | 7,5 | 5% | Contratos aditivos, Ports e stateless permitem incorporar OCR/mobile sem reescrever o núcleo. Retenção, upload e avaliação DCS exigem decisões próprias; não são defeitos por ausência nesta semana. |
| **Geral ponderada** | **7,31** | **100%** | Base funcional sólida; fechamento científico e reprodução ainda exigem correções concretas. |

## 3. Auditoria das alterações de 19/11 e da avaliação automatizada

### 3.1 Commits e mudanças locais

`1451230`, integrado por `76e7be2`/PR #31, resolve a duplicação documental do holdout: `docs/security/protocolo_holdout_guardrail.md` aponta ao protocolo único em `evals/configs/`. A especificação de 40 bloquear + 40 permitir e congelamento anterior à medição é explícita. Entretanto, o Makefile executa o runner com seu default de falso bloqueio igual a 1,0. A documentação foi unificada; a política de aprovação não foi totalmente conectada ao comando.

`91179c8`, integrado por `3df4d8b`/PR #32, adiciona extratores para guardrail, segurança, RAGAS, quatro braços e Semana 4. O código preserva valores numéricos disponíveis em vez de preencher métricas ausentes com qualidade inventada. O diff local acrescenta avaliação S4 e resolve o caminho JSON existente → MLflow ausente. Os testes dos extratores/backfill passaram.

A idempotência não é simétrica: `registrar_avaliacoes.py:357` só consulta a presença no MLflow dentro do caso em que já existe JSON. Se o SQLite contém a execução mas os JSONs locais foram removidos/restaurados parcialmente, `registrar_execucao` cria outra execução nativa. Falha de consulta ao MLflow também retorna `None` indistinguível de biblioteca ausente. Não validei servidor MLflow real nesta revisão; os testes de integração do registrador usam substitutos.

Outro limite do backfill: `_montar_tags` em `mlflow_tracker.py:84` lê o manifesto **atual**. Registrar resultados antigos depois de mudar o corpus pode atribuir a linhagem atual à medição histórica. O hash do artefato continua rastreável, mas não corrige a tag de corpus. Separar identidade do experimento da identidade do ambiente que importou o resultado.

A limpeza de modelos/aliases ociosos não deixou importações quebradas nos 125 arquivos verificados pelo mypy. `already_triaged=True` é usado pelo trabalhador depois da triagem e sanitização do grafo; a rota legada continua com default defensivo `False`. `skip_input_guardrail=True` evita reclassificar o texto já triado; validação do contexto e da saída permanece em `synthesize_guidance.py`. Não encontrei bypass HTTP demonstrável introduzido por essas flags no escopo testado.

O cartão permanece determinístico; a explicação vai para `resposta_adicional`. A seleção de `normative_hits` para pergunta adicional é coerente com as perguntas normativas dos cinco cenários. Timeout maior dá mais tempo ao provedor, **não melhora nem satisfaz RNF04**. O helper de construção reduz divergência entre API e comparativo. `--summary` funcionou nos cinco cenários em modo determinístico.

O fluxo utiliza destinos condicionais em lista, e não instâncias de `Send`, apesar da descrição em `docs/entregaveis_semana4_multiagentes.md`. Isso é imprecisão documental; o paralelismo está implementado e tem teste próprio.

### 3.2 Resultados experimentais preservados

Fonte: cópias de `resultado.json` e `avaliacao_automatica.json` no pacote desta revisão. Denominador: **5 casos por modelo; somente 3 respostas LLM por modelo**. Não extrapolar para população de cidadãos, catálogo inteiro ou segurança clínica geral.

| Medida | Qwen2.5 7B | Qwen2.5 14B |
|---|---:|---:|
| Casos executados/planejados | 5/5 | 5/5 |
| Gerados / abstenção / bloqueio | 3 / 1 / 1 | 3 / 1 / 1 |
| Falhas ou rejeições | 0 | 0 |
| Mediana wall, ms | 6.705,25 | 13.132,39 |
| p95 wall, ms | 17.867,63 | 37.282,84 |
| RNF04 p95 ≤ 8.000 ms | Reprovado | Reprovado |
| Faithfulness RAGAS ≥ 0,92 | 0,8095 — reprovado | 1,0000 — aprovado |
| Answer Relevancy RAGAS ≥ 0,88 | 0,8824 — aprovado | 0,8229 — reprovado |
| Nota composta do runner | 8,25 | 8,25 |
| Nota do juiz | 7,50 | 7,50 |
| Casos com omissões segundo o juiz | 3 | 3 |
| Contradições segundo o juiz | 0 | 0 |
| Revisão humana | Não realizada | Não realizada |

O p95 usa `ceil`; com cinco observações é o máximo observado. A rodada não permite atribuir causalmente toda a diferença ao cold-start, nem concluir superioridade geral de um modelo. “Zero contradições segundo o juiz” não significa ausência verificada de erro factual.

### 3.3 Conferência literal das seis respostas

| Caso | Verificação contra o contexto congelado |
|---|---|
| Helena 7B | Local e regiões correspondem ao chunk CEAF. O texto cita LME, TER e exames; o juiz os enumera como ausentes e trata a lista como não verificável, embora exista no contexto CEAF. InfoSaúde está ausente, mas a pergunta é onde fica a farmácia: a rubrica precisa distinguir resposta pertinente de reprodução de todo o contexto. |
| Lucas 7B | Sinais de alarme, ECG e CNS aparecem no texto e em `CHK-SISREG-001`. A classificação de sinais de alarme como não verificáveis é falso positivo. Há omissão real do encaminhamento/regulação pela UBS da região. Faithfulness 0,4286 é saída registrada do avaliador, não evidência suficiente de que mais da metade da resposta seja falsa. |
| Procuração 7B | Procuração e documentos com CPF estão sustentados. Omite laudo/prescrição de incontinência e outros requisitos presentes nos trechos. O juiz questiona o uso do Farmácia Popular, embora os dois chunks sejam desse programa: falso positivo de enquadramento. |
| Helena 14B | Endereço e documentos têm suporte; “regiões adjacentes” é menos específico que a lista regional, podendo induzir abrangência imprecisa. A falta da enumeração completa não prova, sozinha, falha ao responder à localização em Ceilândia. |
| Lucas 14B | A resposta contém literalmente “eletrocardiograma prévio anexado” e “uma UBS faça a regulação”. O juiz aponta ECG ausente e questiona regulação pela UBS: falso positivo inequívoco. Há menor especificidade sobre CID-10 e UBS da região. |
| Procuração 14B | Inclui laudo de incontinência e procuração com firma reconhecida. O juiz os marca como omitidos: falso positivo inequívoco. Documentos com foto/impossibilidade de locomoção não são explicitados, embora estejam no segundo chunk. |

Esta conferência mede sustentação nos textos congelados do projeto. **Não revalida as normas externas nem certifica que os chunks normativos sejam juridicamente/clínicamente corretos.** A revisão de fontes normativas permanece separada da presença documental F01/F03/F04.

### 3.4 Metodologia do runner

Aspectos sustentados pelo código: usa RAGAS oficial via `ragas.metrics.collections`, contexto recuperado sem gabarito para Faithfulness, schema do juiz validado, métricas finitas, manifesto e checkpoints, marcação explícita de ausência de revisão humana. Context Recall/Precision não são calculados sem gabarito; não devem aparecer como aprovados.

Problemas verificados:

- `_summarize_evaluated_model`, linhas 580–588, usa `gate != REPROVADO`, aceitando `NAO_AVALIADO`. Sonda sintética unitária com uma resposta, juiz 10 e RAGAS ausente retornou `APROVADO_AUTOMATICO_SEM_REVISAO_HUMANA`, métricas RAGAS nulas e RNF04 falso. Isso demonstra o predicado, não desempenho de modelo.
- Não verifica cobertura integral dos cinco cenários para aprovação. Um subconjunto pode ser tratado como avaliação suficiente. Casos desconhecidos recebem rota/status verdadeiros por default em `evaluate_deterministic_case:454`; precisam ficar sem contrato avaliado.
- `main:981` retorna zero independentemente de reprovação/incompletude. Se usado como gate de entrega, o processo passa mesmo com relatório reprovado. Definir códigos explícitos e documentar sua semântica.
- O juiz avalia completude contra todos os requisitos presentes nos trechos, mesmo quando a pergunta pede só endereço. Esse desenho favorece omissões irrelevantes; contradizer literalmente a resposta, porém, é erro do juiz, não apenas severidade da rubrica.
- A nota 8,25 resulta da mistura 30% controles e 70% juiz. Não é nota científica validada nem deve superar os gates reprovados.
- O manifesto da avaliação difere do arquivo atual `semana4_avaliacao.py`; o comparativo tem 87 hashes coincidentes com o código atual e não incluía o novo avaliador. Preservar a avaliação histórica e gerar nova revisão em diretório novo após corrigir o runner, sem editar escores antigos.

## 4. Parecer de portação v10

### 4.1 Validações realizadas na origem isolada

- SHA do candidato `release.json`: `d99e26e52eca0c3b115c9f7d93fa600b2ca4fe39a885cc268c10ff88252e5921`, igual ao registrado na aprovação humana de Jhiovana de 18/11.
- Os nove hashes de arquivos do manifesto conferem. Catálogo candidato: **1.727** registros. Ocorrências e evidências: **2.114** cada.
- Comparação por `occurrence_id` contra staging v9: conjuntos idênticos, zero perda; `raw_text` preservado em todos. Campo `normalized` acrescentado aos 2.114; **148 vínculos `medicine_id` alterados**, **53 componentes preenchidos**, **1 concentração corrigida**. Não confundir 148 ocorrências remapeadas com 132 absorções de entidades declaradas pela origem.
- O candidato permanece `pending_review`, mas existe aprovação humana vinculada ao hash. Após inspecionar o script, reproduzi `approve_v10_release.py` em `/private/tmp`, obtendo release aprovado e chunks v3 válidos: **2.114 textos distintos**.
- Fingerprint de conteúdo aprovado reproduzido: `b7c41f04be50102ee4550647f8d9109af42c2cd1d07ef9cbeb78d608c240ac92`. SHA dos chunks gerados: `d2f415af483ea6700266f8a255db1880d159e0cc140723dbadc7f87f1cb21570`.
- O script usa `date.today()` em `domain_review.json`; a reconstrução de 19/11 não é byte a byte a publicação DVC de 18/11. Não reivindico equivalência do pacote DVC completo. Fixar a data/artefato publicado ao portar.
- A aprovação é de presença documental, normalização e parser F01, sem credenciais clínicas verificadas. As 79 apresentações com forma/concentração ausente não podem comprovar apresentação exata. Há uma linha vazia excluída documentada.

Não refiz OCR dos PDFs nem avaliação dos modelos da origem. Não atribuo alucinação sintética sem evidência. Scripts/resultados experimentais externos não foram aceitos como prova do consumidor development. Licença/permissão de redistribuição não foi estabelecida apenas pelo manifesto; confirmar antes de selecionar código para importação.

### 4.2 Matriz de decisão por artefato ou conjunto coerente

| Artefato da origem | Decisão | Razão e condição no destino |
|---|---|---|
| `docs/reports/v10/revisao-v10-normalizada-jhiovana.md` | Referenciar | Aprovação identificada por hash; preservar escopo documental. |
| `release.json`, `quality_report.json`, `audit_log.jsonl`, `exclusions.jsonl` | Referenciar; importar como proveniência no PR v10 | Conferidos hashes. Arquivar identidade publicada e data; não promover candidato como aprovado por simples cópia. |
| `occurrences.jsonl` | Adaptar | Preservar literal e normalizado; tratar 53 componentes e uma concentração com regressões específicas. Não substituir staging atual durante fechamento. |
| `evidencias.jsonl` | Adaptar | IDs de ocorrência preservados, entidades remapeadas; DTO exige título, seção, página e URL em contrato próprio. |
| `catalog.jsonl` | Adaptar | 1.727 entidades na origem não equivalem a 1.708 no destino; não sobrescrever catálogo `MED-*` com IDs `med-*`. Reconciliar por ocorrência. |
| `normalization.json`, `data/vocab/{ingredients,forms,units,channels}.json` | Adaptar | Úteis para normalização auditável; avaliar regra a regra contra ADR 0006, sais, doses compostas, embalagens e formas ausentes. Não inferir equivalência terapêutica. |
| `id_map_v9_v10.json`, `merges.csv`, `parser_corrections.csv` | Referenciar/importar como trilha | Necessários para explicar absorções e remapeamentos; não são mapa dos IDs canônicos development. |
| `f03_descriptions.json` | Adaptar | Conteúdo de células serve à geração de evidências; preservar origem e hash. |
| Chunks `one-evidence-v3` e seu manifesto | Adaptar | Texto normalizado + literal e metadados novos. Converter ao DTO, regenerar registro de contexto público e verificar segurança/ligação de todos os IDs. |
| `scripts/approve_v10_release.py` | Referenciar/adaptar | Reconstrução validada em isolamento; eliminar volatilidade de data para publicação reproduzível. |
| Scripts de construção/revisão do v10 | Referenciar | Manter como ferramentas da origem; só incorporar a menor transformação necessária ao pipeline development. |
| `src/rag/normalization.py` | Adaptar seletivamente | Arquitetura e regras diferentes. Regressões obrigatórias de doses/associações, insulina genérica, beclometasona e volumes. |
| `src/rag/consolidated.py`, chat/CLI/providers | Cortar da portação direta | Duplicariam recuperação, gerador e governança do destino. Referenciar algoritmos/testes úteis, sem substituir Ports ou guardrails. |
| `src/ingestion/*`, `src/storage/*` | Adiar | Persistência e conectores pertencem a pipeline separado; não são necessários para fechar a orquestração. |
| Datasets `consolidated_v10_reviewed`, `multichunk_v10_benchmark`, `week3_v10_channel_dev_draft` | Adaptar/adiar | IDs, tarefas e splits externos. Dataset rotulado dev/draft não vira holdout. Não modificar Golden Sets para acomodar portação. |
| `evals/results/*`, revisões v9 e relatórios comparativos | Referenciar | Evidência da origem, não números da API development. |
| Vetores, ChromaDB, caches, `data/curation/archive/*`, checkpoints e `.env` | Cortar caches/config; adiar vetorização | Sem necessidade no runtime atual; não importar caminhos locais, segredos ou resultados obsoletos. |
| Normas complementares C01… e integrações vivas | Adiar validação separada | Aprovação v10 se limita F01/F03/F04; não autoriza novas regras de acesso, estoque ou preparo de exames. |

### 4.3 Plano e reversão da futura portação

Preparar staging e derivados em diretório separado; fixar SHA de destino do futuro PR e SHA de origem acima. Registrar hashes, mapa de todas as ocorrências e decisões de alias. Executar baseline e candidata com mesmos Golden v1/v2, matcher, autocomplete, auditoria, bloqueio/abstenção, contexto público, HTTP e Docker. Reexecutar comparativos somente se contexto/código consumidor mudar, mantendo resultados v9 arquivados.

Promover catálogo, evidências, manifesto e registro de contexto como conjunto coerente. Rollback por revert do commit da portação no PR, restaurando o pacote anterior completo; **não** usar checkout de `main` ou sobrescrever mudanças locais. Ativação só após CI e revisão de um membro do squad. Não há evidência nesta auditoria de que v10 já passe no consumidor, porque ele não foi instalado nele.

## 5. Achados priorizados

Não foi reproduzido achado CRÍTICO novo. A ausência de achado não é garantia de ausência de vulnerabilidades.

| Prioridade | Evidência | Problema e impacto | Correção sugerida |
|---|---|---|---|
| **ALTO** | `evals/runners/semana4_avaliacao.py:580` | Aprova com RAGAS não avaliado e amostra parcial; sonda unitária reproduzida. Pode converter ausência de evidência em aprovação. | Exigir gates efetivamente aprovados, completude planejada e separar aprovação de rubrica, ciência e latência. |
| **ALTO** | `backend/tests/unit/test_semana4_avaliacao.py:128`; runner `:647` | Teste de manifesto chama `ollama_identity` antes de detectar incompatibilidade; falha sem rede/Ollama. | Mock explícito de identidade nesse teste e validação local de modo antes de preflight. CI deve passar sem servidor. |
| **ALTO** | `Makefile:155`; `evals/runners/guardrail_runner.py:86` | Holdout permite até 100% de falso bloqueio pelo default, embora protocolo exija ≤5%. Um bloqueador universal satisfaria o recall. | Passar `--max-falso-bloqueio 0.05` às três medições e testar o comando/gate. Não ajustar regras ao holdout. |
| **MÉDIO** | `observability/registrar_avaliacoes.py:357` | Deduplicação depende do JSON local; registro já presente só no MLflow é duplicado. | Tratar os quatro estados JSON/MLflow e impedir duplicação nativa no backfill reverso. |
| **MÉDIO** | `observability/mlflow_tracker.py:84` | Linhagem atual atribuída a backfills históricos. | Extrair identidade do experimento original; tag separada para ambiente de importação. |
| **MÉDIO** | `evals/runners/semana4_avaliacao.py:981` | Saída zero mesmo em reprovação ou avaliação incompleta. | Códigos de saída alinhados ao ADR 0004 ou modo explicitamente informativo, sem uso como gate. |
| **MÉDIO** | `Makefile:166` e `:167` | Compare grava `semana4_comparativo`; eval lê `semana4_comparativo_v2`. Sequência da documentação pode avaliar rodada antiga. | Derivar entrada da avaliação de `S4_RUN_DIR` ou explicitar caminhos únicos por execução. |
| **MÉDIO** | `avaliacao_automatica.json`, casos Lucas/Procuração 14B | Juiz lista como ausente conteúdo presente; nota 8,25 não mede confiabilidade calibrada. | Adjudicar afirmações com evidência literal e nova revisão independente; manter diagnóstico original arquivado. |
| **MÉDIO** | `semana4_avaliacao_v2/manifesto.json` | Hash do avaliador diverge do código atual; retomada bloqueada por identidade. | Publicar artefatos com versão exata, nova rodada/diretório para novo código; nunca reescrever manifesto antigo para fazê-lo passar. |
| **BAIXO** | `docs/entregaveis_semana4_multiagentes.md:15`; `orchestrator.py:60` | Documento chama fan-out de `Send`, classe não usada. | Descrever fan-out por destinos condicionais e barreira explícita. |

## 6. Checklist pré-documento do Teams

### Verificações executadas nesta revisão

| Checagem | Resultado e limite |
|---|---|
| Ruff check / format, a partir de `backend/` | Passou; 133 arquivos formatados. Executar da raiz sem config usa regras diferentes e não reproduz o CI. |
| Mypy nos caminhos do CONTRIBUTING | Passou em 125 arquivos. |
| Pytest backend | 435 passaram + 1 falhou em isolamento; 436 passaram com acesso local ao Ollama. Corrigir dependência antes de afirmar CI íntegra. |
| Evals | 4 testes passaram. |
| Datasets | Seis arquivos válidos; não há holdout independente entre eles. |
| Guardrail de desenvolvimento | Recall 100%, falso bloqueio 0%; não prova generalização. |
| Golden v1/v2 | Gates determinísticos aprovados; 16/22 casos. Precision@3 41,67%/40,74%, nos tetos dos datasets. Roteamento, bloqueio, abstenção e R-Precision 100%. |
| Segurança smoke | Braço C: injeção 4/4, PII 4/4, clínico 4/4. Braços com fixtures não medem modelos reais; injeção indireta do C tem denominador zero. |
| Demo | Cinco cenários determinísticos passaram. |
| HTTP real | Health, autocomplete, sete auditorias e dois grafos passaram em servidor temporário. |
| `git diff --check` | Passou antes da adição deste relatório. |
| `uv lock --check` | Não repetido: `uv` indisponível no PATH e locais usuais; executáveis dos venvs existentes utilizados. A aprovação anterior relatada na documentação não foi verificada aqui. |
| Docker / CI remoto / MLflow nativo | Não executados nesta revisão. Workflow configurado não equivale a job aprovado no commit final. |
| Inferência 7B/14B e RAGAS | Relatórios locais auditados e preservados; não houve nova coleta. |

### Antes do commit final

- [ ] Corrigir os achados ALTOS de gate, isolamento do teste e holdout.
- [ ] Corrigir caminhos do Makefile; documentar códigos de saída e pendências de MLflow.
- [ ] Fazer teste completo sem Ollama/rede, lockcheck, Docker e CI no SHA final.
- [ ] Versionar ou anexar os resultados, manifestos, versões e hashes usados no documento; não depender de arquivos ignorados apenas na máquina do autor.
- [ ] Revisar o texto do Teams para não chamar avaliação automática de revisão humana, nem nota composta de aprovação científica.
- [ ] Manter v9 ativo e registrar v10 como portação proposta para PR separado.
- [ ] Obter revisão de pelo menos um membro do squad conforme CONTRIBUTING.

### O que copiar para o Teams

Copiar a tabela experimental da seção 3.2, com **5 casos por modelo/3 gerações**, o nome do juiz `semana3-qwen14`, embeddings `bge-m3`, RAGAS `0.4.3`, prompt `semana4-v2`, revisão humana `false` e os dois gates reprovados por modelo quando aplicáveis. Não copiar somente 8,25 ou 100% sem denominadores.

Descrever quatro nós LangGraph, três determinísticos e síntese opcional, fan-out paralelo com barreira, ausência de memória de sessão, cartão calculado por código e validação da saída. Registrar corpus **1.708 / 20 / 2.114**, sem substituir pelos **1.727** da origem v10.

Usar como frase de conclusão da entrega: **“Orquestração multiagente implementada e demonstrada; avaliação automatizada exploratória concluída com ressalvas. Metas integrais de qualidade/latência com LLM local e revisão factual humana permanecem pendentes.”** Isso permite documentar trabalho real sem declarar encerrados critérios que os próprios resultados ainda não satisfazem.
