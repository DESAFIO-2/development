# Correções de fechamento da Semana 4 — 19/11/2026

Branch: `codex/correcoes-fechamento-semana4`, criada de
`3df4d8b7ccd243d8679f10d19cb08e8a84c8bda2`, preservando as alterações locais
da revisão geral. O [parecer independente](../reviews/revisao_completa_semana4_2026_11_19.md)
é histórico; esta nota registra as correções posteriores.

## Alterações executadas

- Avaliador `semana4-eval-v2`: exige os cinco cenários, sem repetição ou IDs
  desconhecidos. Casos desconhecidos não recebem aprovação de rota/status.
  RAGAS ausente não aprova; contradições, afirmações não verificáveis, omissões
  e veredito do juiz impedem aprovação automática de qualidade.
- Latência recalculada pelos casos, independentemente do resumo recebido.
  Qualidade, latência e revisão humana são dimensões separadas. Nenhuma saída
  deste avaliador comprova revisão humana. Códigos: 1 incompleto, 2 reprovado,
  3 revisão humana pendente; 0 somente para smoke sintético explícito.
- Incompatibilidade sintético/real é rejeitada antes de consultar Ollama.
  Suíte executada com `socket.socket.connect` bloqueado para comprovar isolamento.
- Rubrica do juiz orienta completude pertinente à pergunta e conferência literal
  das supostas omissões. Não houve nova inferência: essa mudança não é evidência
  de melhora de qualidade do juiz.
- Holdout: limite de falso bloqueio 0,05 aplicado às três camadas do Makefile.
  Nenhum caso de holdout foi criado, alterado ou usado para ajustar regras.
- Coleta/avaliação compartilham `S4_RUN_DIR`; defaults apontam a diretório novo
  `semana4_comparativo_v3`, com avaliação na subpasta `avaliacao`.
- MLflow: backfill JSON → nativo e nativo → JSON sem duplicar o outro destino.
  Falha de consulta nativa adia sincronização. Manifesto atual recebe prefixo
  `ambiente_importacao_*`; linhagem histórica ausente é explicitamente desconhecida.
  Isso não corrige retroativamente tags de runs antigos já gravados.
- Documentação descreve destinos condicionais paralelos, sem atribuir uso da
  classe `Send`. Resultados v1 do avaliador continuam históricos e arquivados.

## Verificação

| Checagem | Resultado |
|---|---|
| Backend sem acesso à rede | **447 passed**, incluindo 11 regressões novas |
| Evals | **4 passed** |
| Ruff lint e formatação | Aprovados, **133 arquivos** |
| Mypy | Aprovado, **125 arquivos** |
| Datasets | Seis arquivos válidos |
| Guardrail de desenvolvimento | Recall 100%, falso bloqueio 0%; não é holdout |
| Golden v1/v2 | Ambos aprovados; Precision@3 41,67%/40,74% nos tetos dos datasets |
| Segurança smoke | API C: injeção 4/4, PII 4/4, clínico 4/4; fixtures não medem LLM |
| Docker | Build `sus-cidadao-backend:s4-review` aprovado |
| Lock no container | `uv lock --check` aprovado, 91 pacotes; build usa `uv sync --locked` |
| HTTP no container | Health, autocomplete, sete auditorias e dois grafos aprovados |
| Diff | `git diff --check` sem erros |

Comandos locais usam `backend/.venv/bin`/`evals/.venv/bin` porque `uv` não está
no PATH do host. Ruff e mypy executados com diretório de trabalho `backend`.
MLflow nativo não está instalado no venv: testes de idempotência usam fixtures
de armazenamento, não certificam disponibilidade de servidor remoto.

## Pendências externas e científicas

CI remoto e revisão do squad dependem de publicação de PR; não foram declarados
aprovados. Após as correções, nova coleta e avaliação completas (`semana4_comparativo_v3`
com rubrica `semana4-eval-v2` + `semana3-qwen14` + `bge-m3` e registro MLflow
`semana4-v3-2026-11-19`) foram executadas, confirmando reprodutibilidade dos escores RAGAS
(`7B`: Faith. `0,8095` / Rel. `0,8824`, `p95 = 19077,00 ms`; `14B`: Faith. `1,0000` /
Rel. `0,8229`, `p95 = 33861,30 ms`; código de saída `2` por gates parciais/RNF04).
Não há revisão humana clínica, nem evidência de cumprimento integral dos gates de
qualidade e latência. A conferência literal das respostas permanece no parecer,
separada das notas originais do juiz.

Corpus v9 permanece ativo (1.708 apresentações, 20 normas e 2.114 evidências).
A triagem v10 e o plano de portação ficam documentados para PR separado da Semana 5;
nenhum dado externo foi promovido nesta correção.

Reversão: reverter a unidade de correções do avaliador, Makefile, registrador e
documentação, preservando artefatos históricos. Não rebaixar metas nem alterar
manifestos antigos para aceitar resultados gerados por código diferente.
