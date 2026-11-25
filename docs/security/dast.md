# DAST gratuito: OWASP ZAP e Schemathesis

Teste dinâmico da API, sem LLM e sem custo. O script
[`scripts/seguranca/dast.sh`](../../scripts/seguranca/dast.sh) é o mesmo no CI
(job `dast` do workflow `security`) e na máquina local (`make dast`).

| Ferramenta | Versão | O que faz |
|---|---|---|
| [OWASP ZAP](https://www.zaproxy.org/docs/docker/api-scan/) (`zap-api-scan.py`) | `ghcr.io/zaproxy/zaproxy:2.17.0` | Lê o `/openapi.json` e ataca cada rota: injeção, XSS, cabeçalhos de segurança, vazamento de erro e de informação |
| [Schemathesis](https://schemathesis.readthedocs.io/) | `4.34.2` | Gera casos válidos e inválidos a partir do OpenAPI e verifica erro 500, respostas fora do contrato e dados inválidos aceitos (`--checks all`) |

## Escopo

Só a API do próprio repositório, construída pelo `backend/Dockerfile` e
rodando num container efêmero com `APP_AGENTS_PROVIDER=deterministic` e STT
desligado (o padrão). Nenhuma chamada sai da API. A porta fica só em
`127.0.0.1`, e o ZAP alcança a API por uma rede Docker dedicada.

Fica de fora tudo que depende de LLM ou de conversa (contornar o guardrail com
um diálogo elaborado, por exemplo). Isso é coberto pelo job `anti-injection` e,
de forma exploratória, pelo [Strix](pentest_strix.md).

## Como rodar localmente (Mac M4 da Eldorado ou Linux)

Requisitos: Docker rodando e [uv](https://docs.astral.sh/uv/). As duas
imagens têm versão `arm64`, então rodam nativas no M4.

```bash
make dast
```

Opções:

| Variável | Padrão | Efeito |
|---|---|---|
| `DAST_DIR` | `output/dast` | Pasta dos relatórios (fora do git) |
| `DAST_PORT` | `8000` | Porta da API em `127.0.0.1`. Troque se a 8000 estiver ocupada |
| `DAST_EXEMPLOS` | `50` | Casos por operação no Schemathesis. Mais casos, mais tempo |
| `SEG_SEM_BUILD` | `0` | `1` reaproveita a imagem `sus-cidadao-backend:seguranca` |

Exemplo: `DAST_PORT=8010 DAST_EXEMPLOS=200 make dast`.

## Relatórios

Em `output/dast/` (no CI, no artifact `relatorio-dast`, guardado por 14 dias):

- `zap/zap.html`, `zap/zap.md`, `zap/zap.json`: alertas do ZAP por risco.
- `schemathesis/`: `junit.xml`, relatório HTML e eventos `ndjson`. Cada falha
  traz um comando `curl` para reproduzir.
- `api.log`: logs da API durante os testes, útil para entender um erro 500.

Códigos de saída: o script retorna 0 só se o ZAP não tiver regra `FAIL` (os
avisos são ignorados com `-I`) e o Schemathesis não tiver falhas.

## Fase de observação

O job `dast` tem `continue-on-error: true`: ele roda em todo PR e na `main`,
mas **não bloqueia o merge** enquanto os achados da primeira execução não forem
triados. A ideia é não deixar o CI vermelho por falso positivo antes de
conhecer a linha de base. Depois da triagem:

1. Corrija os achados reais, cada um com um teste de regressão em
   `backend/tests/`.
2. Para falsos positivos do ZAP, crie um arquivo de regras (`-c`) com a regra
   marcada como `IGNORE` e o motivo. Para os do Schemathesis, exclua a
   verificação específica (`--exclude-checks`) e anote o motivo no script.
3. Remova `continue-on-error: true` do job.

Os logs e artifacts de um repositório público são visíveis para qualquer
pessoa logada no GitHub. Os achados do ZAP e do Schemathesis são, em geral, de
robustez (erro 500, cabeçalho ausente), e qualquer pessoa poderia gerá-los
rodando as mesmas ferramentas abertas. Se algum se mostrar explorável de
verdade, siga o [SECURITY.md](../../SECURITY.md) e corrija antes de discutir
os detalhes em issue ou PR público.

## Reversão

Remova o job `dast` de `.github/workflows/security.yml`, o alvo `dast` do
`Makefile`, `scripts/seguranca/dast.sh` (e `_api.sh`, se o Strix também sair)
e este documento.
