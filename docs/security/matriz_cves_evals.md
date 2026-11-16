# Matriz de Auditoria de CVEs — Ambiente Isolado `evals/` vs Runtime `backend/`

**Data:** 2026-11-16  
**Escopo:** Isolamento entre dependências de avaliação offline ([evals/pyproject.toml](../../evals/pyproject.toml)) e runtime da API ([backend/pyproject.toml](../../backend/pyproject.toml)).

## 1. Runtime (`backend/uv.lock`) — Zero Exceções

- `dnspython` atualizado de `2.9.1` para `2.9.2` (`CVE-2026-128089`).
- A imagem Docker (`backend/Dockerfile`) instala exclusivamente `backend/uv.lock --no-dev` e não contém `ragas`, `langchain*` nem `diskcache`.
- O workflow [security.yml](../../.github/workflows/security.yml) audita `backend/uv.lock` sem nenhuma flag `--ignore-vuln`.

## 2. Ambiente Isolado de Avaliação (`evals/uv.lock`)

O avaliador científico oficial depende de `ragas==0.4.3`, que importa `langchain_community.chat_models.vertexai` e exige explicitamente `langchain<1`, `langchain-community<0.4` e `langchain-openai<1`. As versões travadas em `evals/uv.lock` já estão no teto disponível compatível com o ramo `0.3.x`, enquanto os fixes publicados para os pacotes `langchain*` pertencem ao ramo `1.x`.

Para que o CI continue reprovando **qualquer vulnerabilidade nova** em `evals/uv.lock` sem quebrar o `ragas==0.4.3`, apenas os **7 IDs já auditados abaixo** recebem `--ignore-vuln` explícito em `.github/workflows/security.yml`:

| Pacote (`evals/uv.lock`) | Versão Travada | ID da Vulnerabilidade | Fix Publicado | Motivo da Exceção Transitória |
| --- | --- | --- | --- | --- |
| `diskcache` | `5.6.3` | `PYSEC-2026-2447` | Sem fix publicado | Dependência transitiva de `ragas==0.4.3`; uso estrito em benchmark local offline sem tráfego externo não confiável. |
| `langchain` | `0.3.30` | `PYSEC-2026-2192` | `1.3.9` | Exige upgrade para `langchain>=1`, incompatível com `ragas==0.4.3` (`langchain<1`). |
| `langchain-core` | `0.3.86` | `PYSEC-2026-2193` | `1.2.22` | Bloqueado por `langchain==0.3.30` e `ragas==0.4.3`. |
| `langchain-core` | `0.3.86` | `PYSEC-2026-2562` | `1.2.11` | Bloqueado por `langchain==0.3.30` e `ragas==0.4.3`. |
| `langchain-text-splitters` | `0.3.11` | `PYSEC-2026-77` | `1.1.2` | Bloqueado por `langchain==0.3.30`. |
| `langchain-openai` | `0.3.35` | `PYSEC-2026-76` | `1.1.14` | Exige `langchain-core>=1`, incompatível com `evals/pyproject.toml` (`langchain-openai<1`). |
| `ragas` | `0.4.3` | `PYSEC-2026-3046` | Sem fix publicado | Versão fixada pelo `ADR 0004` exclusivamente para avaliação offline de métricas. |

## 3. Critério de Remoção da Exceção

- Atualizar/remover `--ignore-vuln` assim que `ragas` publicar versão estável compatível com `langchain>=1.3.9` e `langchain-core>=1.2.22`, ou quando o avaliador oficial for migrado na etapa pós-Semana 4.
- Jamais importar `evals/` no runtime da API FastAPI ou adicionar esses pacotes a `backend/pyproject.toml`.
