> Atualização de 11/11/2026: este registro contém resultados históricos da portação.
> Para o protocolo corrigido e a retirada dos resultados sintéticos como evidência científica,
> consulte [o entregável atualizado](entregaveis_semana3_comparativo.md) e o ADR 0004.

# Auditoria técnica e entrega da semana 3

> Esta auditoria registra a linha de base anterior ao v5. Veja as mudanças e os resultados atuais no [registro da portação](implementation/plano_semana3_corpus_v5.md#registro-da-portação-executada).

## Fluxo disponível

A API FastAPI carrega o catálogo consolidado e os chunks normativos locais na inicialização. O autocomplete consulta o catálogo por DCB. A auditoria recebe itens estruturados, aplica o guardrail clínico, mascara identificadores reconhecidos nos campos encaminhados à busca e usa o catálogo para orientar a dispensação. A busca lexical híbrida (DCB, BM25 e TF-IDF com RRF) recupera trechos normativos. A resposta atual usa templates determinísticos.

| Validação local | Resultado |
| --- | --- |
| Catálogo, chunks e staging | 1.789 registros canônicos, 20 chunks normativos e 70 chunks unificados. Os quatro SHA-256 individuais do manifesto correspondem aos arquivos. |
| API via ASGI | Health, autocomplete e auditoria com o corpus real, incluindo Farmácia Popular, CEAF, SISREG e abstenção. O sandbox bloqueou a abertura de socket para o smoke via Uvicorn. |
| Guardrail clínico | Recall de bloqueio de 100% e falso bloqueio de 0% no dataset versionado. |
| Golden Set v1 | 16 casos, 100% em Hit@3, Recall@3, roteamento, bloqueio e abstenção. MRR de 1,0. |
| Golden Set v2 | 22 casos, 18/18 (100%) no roteamento positivo, 100% em Hit@3, Recall@3, bloqueio e abstenção. MRR de 1,0. |
| Comparativo LLM × RAG | 22 casos pareados (`comparar_semana3.py`): roteamento subiu de 16,67% (sem RAG) para 100,00% (com RAG), alucinação factual caiu de 77,27% para 0,00% e Faithfulness subiu de 0,1780 para 0,9754. |
| Docker | O Dockerfile inclui o corpus e a CI testa o carregamento da imagem. O daemon local estava indisponível para executar o build. |

O benchmark usa a pergunta original, mede a rota do primeiro cartão e registra as divergências por ID. Consultas com vários itens precisam de um fixture estruturado com a rota esperada por apresentação para medir a cobertura integral. A aprovação exige todos os critérios determinísticos da spec. O v2 fica informativo na CI enquanto a divergência abaixo estiver aberta.

## Pendências da aplicação

| Prioridade | Evidência e condição para fechar |
| --- | --- |
| Alta | `GOLD-020` reúne benzilpenicilina benzatina e medroxiprogesterona sob uma rota esperada de UBS. O fluxo de consulta livre escolhe um candidato e retorna Farmácia Popular. Separar os itens, revisar o rótulo com a frente de dados e testar as duas apresentações na API. |
| Alta | O ETL propaga a cobertura do Farmácia Popular pelo nome do princípio ativo. Por exemplo, a medroxiprogesterona oral de 10 mg tem rota PFPB embora o próprio registro aponte apenas F01. Reconciliar F04 por apresentação e confirmar as divergências com a curadoria. |
| Alta | A classificação agrega Policlínicas, HUB, CEDIN e componente estratégico na rota de UBS. O canal específico fica em `notes` e o cartão usa um texto genérico. Separar canal local, elegibilidade e fonte/página por ocorrência. A citação agora usa a procedência gravada no catálogo, cujas páginas ainda precisam de validação nos registros consolidados. |
| Alta | A dúvida adicional é usada pelo guardrail, e a resposta administrativa é produzida a partir dos itens. Tratar dúvidas de documentação e logística como parte do fluxo e confirmar regras e validade por item. O mascarador cobre padrões conhecidos e requer validação de ponta a ponta antes de qualquer uso de dados reais com um provedor externo. |
| Média | O retriever em produção usa 20 chunks normativos. Os 70 chunks unificados, estoque InfoSaúde, geolocalização e Chroma estão fora do fluxo HTTP. Mobile, carteira, notificações, OCR/voz, multiagentes e DCS continuam no roadmap. |

O contrato da auditoria agora inclui `HOSPITALAR`. Em `NAO_PADRONIZADO` sem cobertura confirmada, os três campos de validade podem ser `null`. Clientes devem tratar esses valores antes de exibir contagem regressiva.

## Handoff do comparativo

O ponto de entrada é [comparar_caso](../evals/runners/comparar_semana3.py). Ele recebe a mesma pergunta, o mesmo gerador e o mesmo retriever. O braço sem recuperação recebe uma tupla vazia e o braço RAG recebe os trechos Top-K com seus metadados. A referência segue para avaliação após a geração. O contrato é importável com a raiz do repositório e `backend/` no `PYTHONPATH`.

1. Usar o `golden_set_v2_consolidado.jsonl` com casos congelados por ID e SHA-256. Manter o v1 como regressão. Revisar casos compostos antes de usar os resultados como evidência de qualidade.
2. Implementar um adaptador de geração e a CLI de comparação. Fixar modelo e versão, prompt de sistema, temperatura e configuração nos dois braços. Aplicar o mesmo guardrail e contabilizar separadamente os casos bloqueados, de abstenção e de falha de geração.
3. Medir correção de rota, citação, resposta relevante, abstenção e segurança nos dois braços. Medir faithfulness, context recall e context precision no braço com evidências. Marcar métricas de contexto do braço sem recuperação como não aplicáveis. Fixar também o modelo avaliador e revisar divergências por amostra humana.
4. Persistir respostas, evidências, métricas por caso e agregadas, latência, erros e linhagem. Reusar `MLflowExperimentTracker` para vincular os resultados ao dataset, corpus, versões e configuração. Entregar tabela por braço e delta pareado, com denominadores e exemplos de acertos e falhas.

O experimento comparativo completo foi implementado e validado em [comparar_semana3.py](../evals/runners/comparar_semana3.py) com adaptadores `GeneratorPort` em [generator.py](../backend/app/infrastructure/llm/generator.py) e documentado em [entregaveis_semana3_comparativo.md](entregaveis_semana3_comparativo.md).
