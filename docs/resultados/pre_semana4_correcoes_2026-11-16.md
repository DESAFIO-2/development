# Correções da auditoria pré-Semana 4 — 2026-11-16

## Escopo e rastreabilidade

Correção dos três achados reproduzidos: exceção administrativa liberando pedidos
clínicos, emergência indevida em negação/histórico e aprovação de PDF cuja inspeção
não terminou. Inclui regressões, ADR 0005 e smoke HTTP do container no CI.
Não inicia a Semana 4 nem altera os resultados científicos da Semana 3.

Repositório: `https://github.com/DESAFIO-2/development.git`.

| Referência inicial | SHA fixado |
| --- | --- |
| `main` local e remota | `f30644f6505ab07d5cb84b6d2b96450e9432a68d` |
| `fix/pre-semana4-seguranca-ci-base` | `254ee8a97370e72c288ef10f8d63d1d1e3252342` |
| `feat/pre-semana4-corpus-v9` | `6cfc5e000516be4ef3b194a3c5c854c7874794ec` |

Árvore de trabalho inicialmente limpa. `git ls-remote --heads` não encontrou as
duas branches de trabalho no remoto. Referências locais de recuperação criadas:
`backup/pre4-seguranca-20261116` e `backup/pre4-corpus-20261116`.

| Artefato | Decisão |
| --- | --- |
| Guardrail, scanner PDF, testes e CI | Adaptar na branch de segurança |
| Dois commits exclusivos do corpus | Reaplicar sobre a segurança corrigida, sem duplicação |
| Corpus, datasets, schemas e lockfiles | Preservar; não importar versões novas |
| Docker build/HTTP em container | Validação pendente em host com Docker ou CI |
| Merge, push e funcionalidades da Semana 4 | Fora desta execução |

## Resultados na branch de segurança

Ambiente Windows, Python 3.12.16, dependências dos lockfiles existentes.
A linha de base tinha **200 testes passando**. Depois da correção:

| Verificação | Resultado observado |
| --- | --- |
| Pytest backend | **266 passaram** |
| Pytest do ambiente isolado `evals/` | **1 passou**, SDK RAGAS com HTTP simulado |
| Ruff lint / format | Sem violações; 101 arquivos formatados |
| Mypy | Sem erros em 98 arquivos |
| Sincronização `uv sync --locked --check` | Nenhuma alteração necessária |
| Validação estrutural dos datasets | Cinco datasets válidos |
| Guardrail clínico v1 | 25/25 bloqueios esperados; 0/20 falsos bloqueios |
| Segurança determinística, braço C | Injeção 4/4; PII 4/4; clínico 4/4 |
| HTTP real, Uvicorn em loopback | Health, autocomplete e sete auditorias passaram |
| Smoke do comparativo | Zero pares inválidos; RAGAS/factualidade não avaliados |
| Bandit `backend/app`, limiar médio/alto | Sem achados no limiar; uma verificação desabilitada registrada pelo scanner |

O smoke de segurança usa fixtures para A/B/D: suas eliminações não medem qualidade
de modelos. O resultado de C exercita a aplicação determinística em casos sintéticos.

| Recuperação determinística | Golden Set v1 | Golden Set v2 |
| --- | ---: | ---: |
| Casos | 16 | 22 |
| Hit@3 / Recall@3 / Precision@1 / R-Precision | 100% | 100% |
| MRR / nDCG@3 | 1,0 | 1,0 |
| Precision@3 | 41,67% | 40,74% |
| Teto de Precision@3 do dataset | 41,67% | 40,74% |
| Acurácia de roteamento | 100% | 100% |

Os casos são conjuntos de desenvolvimento/regressão; não são teste independente
de generalização. Não houve inferência real de LLM nem nova auditoria factual.

## Reprodução das checagens

Da raiz do repositório, PowerShell:

```powershell
Push-Location backend
uv sync --locked --check
uv run --locked pytest -q
uv run --locked ruff check . ../evals ../observability
uv run --locked ruff format --check . ../evals ../observability
uv run --locked mypy app tests ../evals/runners ../evals/baselines ../observability
Pop-Location
uv run --locked --project evals pytest evals/tests -q
uv run --locked --project backend python evals/runners/validar_datasets.py
uv run --locked --project backend python evals/runners/guardrail_runner.py --alvo app.guardrails.clinical:deve_bloquear --min-recall 1 --max-falso-bloqueio 0
uv run --locked --project backend python evals/runners/suite_seguranca.py --synthetic-smoke --fail-on-api-elim
uv run --locked --project backend python evals/runners/ragas_runner.py --dataset evals/datasets/golden_set_v1.jsonl
uv run --locked --project backend python evals/runners/ragas_runner.py --dataset evals/datasets/golden_set_v2_consolidado.jsonl
uv run --locked --project backend python evals/runners/comparar_semana3.py --synthetic-smoke
uv tool run bandit -r backend/app -ll
```

Para HTTP real, iniciar `uv run --locked uvicorn app.main:app --host 127.0.0.1
--port 18743` **dentro de `backend/`**, mantendo o terminal aberto. Em outro terminal,
na raiz, executar `uv run --locked --project backend python backend/tests/smoke_http.py
--base-url http://127.0.0.1:18743`. Encerrar somente o servidor iniciado para esse teste.

## Limitações e reversão

Docker não está instalado neste host. O novo job inicia a imagem, aguarda health
com prazo, verifica HTTP e remove o container ao terminar; sua execução ainda não
foi comprovada. Não houve push nem disparo de CI nesta etapa.

O scanner PDF limita sua travessia, mas não oferece isolamento de recursos do
parser/descompressor. Regras clínicas são heurísticas conservadoras, não triagem.
Não foram alteradas dependências; esta execução não refaz a auditoria de CVEs.

A reversão das correções pode ser feita por revert do commit de segurança; isso
reintroduz os achados. As referências de recuperação preservam os dois históricos
anteriores ao rebase. Não usar reset destrutivo sobre trabalho posterior.

A ordem futura de integração é segurança antes de corpus. Se houver squash da
segurança, reaplicar somente os commits exclusivos do corpus sobre a `main`
atualizada. Nenhuma integração em `main` faz parte desta execução.
