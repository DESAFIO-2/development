# DAST gratuito: OWASP ZAP e Schemathesis

Teste dinâmico da API, sem LLM e sem custo. O script
[`scripts/seguranca/dast.sh`](../../scripts/seguranca/dast.sh) é o mesmo no CI
(job `dast` do workflow `security`) e na máquina local (`make dast`).

| Ferramenta | Versão | O que faz |
|---|---|---|
| [OWASP ZAP](https://www.zaproxy.org/docs/docker/api-scan/) (`zap-api-scan.py`) | `ghcr.io/zaproxy/zaproxy:2.17.0` | Lê o `/openapi.json` e ataca cada rota: injeção, XSS, cabeçalhos de segurança, vazamento de erro e de informação |
| [Schemathesis](https://schemathesis.readthedocs.io/) | `4.34.2` | Gera casos válidos e inválidos a partir do OpenAPI e verifica erro 500, respostas fora do contrato e dados inválidos aceitos (todas as verificações, com as exceções justificadas em `scripts/seguranca/schemathesis.toml`) |

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

## Bloqueio e exceções

O job `dast` **bloqueia o merge**: o script só retorna 0 se o ZAP não tiver
regra `FAIL` e o Schemathesis não tiver falhas. Para um achado novo:

1. Se for real, corrija com um teste de regressão em
   [`backend/tests/security/test_contrato_dast.py`](../../backend/tests/security/test_contrato_dast.py).
2. Se for falso positivo do Schemathesis, desligue só a verificação e só na rota
   afetada em [`scripts/seguranca/schemathesis.toml`](../../scripts/seguranca/schemathesis.toml),
   com o motivo ao lado. Para o ZAP, use um arquivo de regras (`-c`) com a regra
   como `IGNORE` e o motivo.

Nunca desligue uma verificação para todas as rotas sem justificar no arquivo
por que ela não se aplica a nenhuma.

## Primeira triagem (25/11/2026)

Primeira execução no PR #36: o ZAP passou em 118 regras com 2 avisos, e o
Schemathesis achou 8 falhas em 307 casos. Nenhum erro 500. Corrigir as
primeiras revelou outras mais fundas, e todas foram tratadas:

| Achado | Ferramenta | Tipo | Tratamento |
|---|---|---|---|
| Faltavam `X-Content-Type-Options` e `Cross-Origin-Resource-Policy` | ZAP (aviso) | Real | Middleware `aplicar_cabecalhos_seguranca` em toda resposta, inclusive de erro |
| 400, 413 e 415 não documentados no OpenAPI | Schemathesis ST103 | Contrato | `responses=` nas três rotas (`app/api/schemas/erro.py`) |
| `"data_emissao": 0` aceito como 01/01/1970 | Schemathesis ST201 | **Real** | `DataISO`: só `AAAA-MM-DD` |
| `"0\r"` passava no schema e virava `"0"` depois do strip | Schemathesis ST202 | Contrato | Padrão "2 caracteres visíveis", o mesmo no OpenAPI e no Pydantic (`regex_engine="python-re"` e classe de espaços explícita) |
| "Itens ou pergunta" fora do contrato do `/orchestrate` | Schemathesis ST202 | Contrato | `anyOf` no schema e a mesma regra (`tem_visivel`) no validador |
| `confirmado_pelo_usuario` aceitava `"0"`, `"yes"`, `"on"` | Schemathesis ST201 | **Real** | Só `"true"` ou `"false"`, que é o que todos os clientes já mandam |
| `data_emissao` com espaços virava "não informada" | Schemathesis ST201 | Real | Só o campo vazio conta como não informado, como diz o contrato |
| `pdf_file`/`audio_file` como texto eram ignorados em silêncio | Schemathesis ST201 | Real | 422 |
| Data futura, conteúdo de arquivo e JSON de `itens_json` rejeitados | Schemathesis ST202 | Falso positivo | `positive_data_acceptance` desligado: são regras de negócio que o OpenAPI não expressa |
| Mutação de tipo (null, array) em campo de multipart | Schemathesis ST201 | Falso positivo | `negative_data_rejection` desligado **só** no multimodal: no multipart tudo vira texto ou bytes |

Validação: as cinco seeds testadas (a do CI e mais quatro, com até 100 casos
por operação, mais de 3.900 casos no total) passaram sem falha. Com a correção
da data revertida de propósito, o Schemathesis voltou a acusá-la nas duas rotas
JSON, o que confirma que a exceção do multimodal não desligou a verificação nas
outras.

Os logs e artifacts de um repositório público são visíveis para qualquer
pessoa logada no GitHub. Os achados do ZAP e do Schemathesis são, em geral, de
robustez (erro 500, cabeçalho ausente), e qualquer pessoa poderia gerá-los
rodando as mesmas ferramentas abertas. Se algum se mostrar explorável de
verdade, siga o [SECURITY.md](../../SECURITY.md) e corrija antes de discutir
os detalhes em issue ou PR público.

## Reversão

Remova o job `dast` de `.github/workflows/security.yml`, o alvo `dast` do
`Makefile`, `scripts/seguranca/dast.sh`, `scripts/seguranca/schemathesis.toml` (e `_api.sh`, se o Strix também sair)
e este documento.
