# Guia de Contribuição - SUS Cidadão (NavegaSUS)

Obrigado por contribuir com o projeto do Challenge 2 (Residência em IA Instituto Eldorado / UnB / Softex / MCTI).

## 🌳 Fluxo de Trabalho Git (GitFlow Simplificado)

1. **Branch Principal:** `main` (código testado, auditado e estável).
2. **Branches de Feature:** nomeadas como `feat/<funcionalidade>` ou `fix/<correcao>`.
3. **Pull Requests (PRs):**
   - Todo código novo entra exclusivamente via PR.
   - Todo PR deve passar obrigatoriamente pelas checagens de CI (Ruff, Mypy, Pytest).
   - Revisão obrigatória de pelo menos 1 membro do squad (conforme definido no `.github/CODEOWNERS`).

## 🛠️ Padrões de Qualidade de Código

Antes de abrir um PR ou realizar um commit, certifique-se de executar:

```bash
make format   # Formata com Ruff
make lint     # Valida tipagem com Mypy e regras com Ruff
make test     # Roda a suíte de testes unitários e de integração
```

## 📜 Registros de Decisões de Arquitetura (ADRs)

Qualquer alteração estrutural no domínio, na recuperação RAG ou nos guardrails deve ser acompanhada de um ADR na pasta `docs/adr/`.
