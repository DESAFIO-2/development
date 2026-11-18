# Portação dos agentes — Semana 4

## Origem e destino fixados antes da implementação

- Destino: `DESAFIO-2/development`, base `72f347b74224f14ae6244a048e098b42d410aa40`.
- Branch autorizada: `feat/semana4-multiagentes`; checkout inicialmente limpo.
- Origem: https://github.com/DESAFIO-2/data-science, `main`,
  `7d9e9bc1148eb9a9804fab24b9e6b91f563302a6`; referências remotas conferidas em 17/11/2026.
- Última revisão de portação de DS: `d1f8fe1bf43b7c45e88d6b6907166845d0281601`.
  Comparado o intervalo até a origem atual, incluindo grafo, portas e testes SPEC-11.
- Origem inspecionada em checkout isolado, sem executar seus pipelines.

## Decisões por artefato

| Artefato | Decisão |
| --- | --- |
| Topologia de quatro nós e fan-out de Marlon | Adaptar como implementação própria sobre contratos oficiais; reconhecer a contribuição da topologia e evidências por ocorrência. |
| Ports, container e trace do DS | Referenciar; reutilizar os equivalentes existentes no destino. |
| Catálogo/guardrails/matcher/evals do DS | Não importar: preservar revisão reconciliada, ADR 0006 e protocolo científico do destino. |
| Evidências v2 | Ativar as já aprovadas no destino; nenhuma importação de dados nesta portação. |
| Memória SQLite/checkpointer, voz, UI, PDFs derivados | Adiar para escopo e validação próprios. Requisição stateless nesta semana. |
| Estoque/unidades locais | Adiar ativação: snapshot não prova disponibilidade atual; não criar Ports sem consumidor necessário nesta entrega. |
| Métricas RAGAS do DS | Apenas referenciar a auditoria anterior; não usar como evidência empírica. |

Não se copiam arquivos externos nem binários; adaptação de padrão arquitetural e
integração com código do próprio destino. Não se amplia o escopo de aprovação dos dados.

## Linha de base

`uv run --project backend pytest backend/tests -q`: **358 passed, 2 failed**.
As duas falhas pré-existentes são `UnicodeDecodeError` em leituras sem `encoding`
em `test_curated_consolidation.py`, no Windows CP1252. Corrigir explicitamente UTF-8.

## Contratos, ativação e reversão

Nova rota aditiva `/api/v1/agents/orchestrate`; `/prescriptions/audit` preservada.
LangGraph restrito ao adaptador de orquestração, dependências fixadas em `uv.lock`.
Modo determinístico explícito por padrão; geração exige configuração consciente de
provedor/modelo. Falhas visíveis e modo estrito para coleta, sem fallback científico.
Docker já inclui as três bases necessárias; nenhuma nova base é introduzida.

Para reverter após integração, reverter o commit/PR completo (grafo, contratos,
composição, dependências, testes e documentação), mantendo dados e endpoint legado.
Antes da integração, o diff desta branch contra a base acima é a unidade de revisão.
Não promover a main sem CI e revisão de membro do squad (CONTRIBUTING/CODEOWNERS).

## Dados preservados e hashes SHA-256

| Arquivo em `data/processed/` | Contagem | SHA-256 |
| --- | ---: | --- |
| `medicamentos_sus_canonical.json` | 1708 | `c2f3ccc9da66842b5113c715202c5ba0b46e5bf633e4881aa8b4c7a404da9466` |
| `normative_chunks.json` | 20 | `4e69c4c4fba158905f6bee19e5dd79d9db7032e5f3679c04ca2a6744f9801c3d` |
| `evidence_chunks_v2.json` | 2114 | `458749503f20cb5bd9a218a1021320dec226fbcabe6bfb9ef76e2df9da8348ba` |

Schema continua `2026.4.0`, evidências `one-evidence-v2`. `git diff -- data evals`
sem mudanças: não alterar datasets/gabaritos para a candidata. Fonte/título/página
de cada evidência vêm dos metadados existentes; títulos das evidências literais
usam a identificação de edição `source.version`.

## Higiene conservadora

Busca por referências no repositório confirmou que `embedding_model_name`,
`vector_store_path`, `openai_api_key` e `anthropic_api_key` não têm consumidores.
Removidos de Settings/exemplos quando presentes. Não remover `bge-m3` dos runners:
tem consumidor real no ambiente de avaliação, separado da API.
`extract_rename_full.py` tem referências históricas na entrega da Semana 2;
preservado com aviso de legado e indicação do consolidador vigente. Nenhum arquivo
de dados foi removido. LangSmith é dependência direta para desabilitar explicitamente
tracing de estado; sua presença não ativa serviço nem requer conta/chave.

## Validação e revisão final

Ambiente: Windows, Python 3.12 via uv, LangGraph 1.2.22 resolvido no lockfile.
Comandos de Ruff/Mypy executados a partir de `backend/`, como a CI, para usar
o mesmo arquivo de configuração. A invocação inicial da raiz descobriu regras
externas diferentes para `evals/`; não se alteraram os arquivos de avaliação
para acomodar essa invocação fora do procedimento.

| Verificação | Resultado |
| --- | --- |
| `uv run pytest -q` em backend | 410 passed (inclui contrato multiagente, isolamento, correções P1/P2, autocomplete DCB numérica e comparativo Semana 4) |
| Ruff check + format check, escopo de CI | Sem erros; 129 arquivos verificados |
| Mypy strict app/tests/runners/baselines/observability | Sem erros em 121 arquivos |
| `uv lock --project backend --check` | Resolvido e consistente (91 pacotes, incluindo grupos) |
| `uv run --project evals pytest evals/tests -q` | 4 passed; transporte/SDK simulados, não qualidade LLM |
| `validar_datasets.py` e `guardrail_runner.py` | 6 datasets íntegros; recall de bloqueio 100,00% e falso bloqueio 0,00% |
| `ragas_runner.py --dataset ...golden_set_v1.jsonl` | Gates determinísticos aprovados, 16 casos |
| `ragas_runner.py --dataset ...golden_set_v2_consolidado.jsonl` | Gates determinísticos aprovados, 22 casos |
| `suite_seguranca.py --synthetic-smoke --fail-on-api-elim` | API legada C aprovada (4/4 por dimensão aplicável); A/B/D fixtures não medem LLM |
| `smoke_http.py` contra Uvicorn real | health, autocomplete, 7 auditorias e 2 grafos aprovados |
| CLI `python -m app.agents.demo` | 5 cenários reproduzíveis (Dona Helena, Lucas, procuração/fralda, abstenção, bloqueio), 4 traces e citações |
| `semana4_comparativo.py --synthetic-smoke --pilot` | Encanamento com checkpoints validado (`SMOKE_SINTETICO_NAO_E_EVIDENCIA`) |
| Docker local | Não executado: binário/daemon indisponível neste ambiente; gate CI continua obrigatório |
| LLM real (`qwen2.5:7b` vs `14b`) no MacBook | `NAO_AVALIADO`: MacBook/Ollama indisponível neste host; roteiro pronto via `make semana4-pilot` / `make semana4-compare` |

Resultados transitórios do smoke em `evals/reports/semana4-validation/` (ignorados
pelo Git). Relatórios determinísticos existentes em `evals/reports/`; não publicar
os smokes como benchmark dos agentes. Os testes novos usam fakes somente em `tests/`.

Revisão do diff: rota legada não usa o novo gerador; concentração, validade e
documentação permanecem no caso de uso existente; fluxo novo não tem banco de
sessões, frontend, dados externos copiados, ferramentas de voz ou chamada REST
paralela por fora de GeneratorPort. O 7B é candidato operacional, não modelo
cientificamente aprovado. ADR 0007 registra limitações e próximos gates.

O clone isolado de leitura `C:\development-ds-review-20261117` permanece no host:
a política de execução bloqueou sua remoção ao final. Ele não integra o diff do
development e nenhuma alteração foi feita no repositório remoto de origem.
