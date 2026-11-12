## Resumo
<!-- Descreva objetivamente o que muda e por quê. -->

- **Issue vinculada:** Closes #
- **Frente:** <!-- IA & Agentes | Arquitetura/API/Mobile | Eng. Dados | Ciência de Dados | MLOps/LLMOps -->
- **Semana do Roadmap:** <!-- Semana 3 | Semana 4 | Semana 5 | Semana 6 | Semana 7 -->

## Conferência de Qualidade (`CONTRIBUTING.md`)
- [ ] `make format` executado sem pendências
- [ ] `make lint` (Ruff + Mypy) aprovado sem erros
- [ ] `make test` (testes unitários e de integração) aprovado
- [ ] Alteração restrita ao escopo da Issue vinculada (sem mudanças paralelas não intencionais)

## Integridade Científica & Portações (quando aplicável)
- [ ] Se envolver IA/evals: cumpre o [ADR 0004](docs/adr/0004_integridade_comparativo_semana3.md) e as [Diretrizes de Integridade Científica](docs/runbooks/diretrizes_integridade_ia.md) (sem mocks como evidência empírica, sem fallback silencioso, métricas não medidas mantidas como `NAO_AVALIADO`).
- [ ] Se envolver portação de outro repo/branch: segue o [Runbook de Portações](docs/runbooks/portacoes.md) (SHA de origem fixado, decisão por artefato registrada, validação no consumidor e plano de reversão).
- [ ] Se alterar domínio, RAG ou guardrails: ADR correspondente criado/atualizado em `docs/adr/`.
