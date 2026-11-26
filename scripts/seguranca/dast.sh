#!/usr/bin/env bash
# DAST gratuito, sem LLM: OWASP ZAP (API scan) e Schemathesis contra a API do
# backend rodando num container efêmero. Mesmo script no CI e na máquina local.
# Detalhes e triagem: docs/security/dast.md
#
# Uso (da raiz do repositório): make dast
# Variáveis opcionais:
#   DAST_DIR=output/dast   pasta dos relatórios
#   DAST_PORT=8000         porta local da API (só em 127.0.0.1)
#   DAST_EXEMPLOS=50       casos gerados por operação no Schemathesis
#   SEG_SEM_BUILD=1        reaproveita a imagem já construída
set -euo pipefail

ZAP_IMAGE="ghcr.io/zaproxy/zaproxy:2.17.0"
SCHEMATHESIS_VERSION="4.34.2"

# shellcheck source=scripts/seguranca/_api.sh
source "$(dirname "$0")/_api.sh"

SAIDA="${DAST_DIR:-output/dast}"
PORTA="${DAST_PORT:-8000}"
EXEMPLOS="${DAST_EXEMPLOS:-50}"
REDE="sus-cidadao-dast"
API="sus-cidadao-dast-api"

seg_checar_ferramentas

rm -rf "$SAIDA"
mkdir -p "$SAIDA/zap" "$SAIDA/schemathesis"
SAIDA="$(cd "$SAIDA" && pwd)"
# O container do ZAP roda com o usuário "zap" e precisa escrever aqui.
chmod 777 "$SAIDA/zap"

limpar() {
  api_derrubar "$API" "$SAIDA/api.log"
  docker network rm "$REDE" > /dev/null 2>&1 || true
}
trap limpar EXIT
limpar  # sobra de uma execução interrompida

api_build
docker network create "$REDE" > /dev/null
# Login obrigatório (como em produção) para o DAST exercitar a autenticação:
# sem token tem de dar 401, e com o token as rotas protegidas são testadas a fundo.
# Access token de 60 min para cobrir a rodada inteira. Rate limit segue desligado
# (ambiente local), senão o fuzzing viraria uma sequência de 429.
API_ENV_EXTRA=(-e APP_AUTH_OBRIGATORIA=true -e APP_AUTH_ACCESS_TTL_MIN=60)
api_subir "$API" 127.0.0.1 "$PORTA" "$REDE"
TOKEN="$(api_token "http://127.0.0.1:${PORTA}")"
[ -n "$TOKEN" ] || { echo "Não consegui criar o usuário do DAST." >&2; exit 1; }

# --- OWASP ZAP -------------------------------------------------------------
# Códigos: 0 ok, 1 alguma regra FAIL, 2 só avisos (ignorados com -I), 3 erro.
echo "== OWASP ZAP (API scan)"
set +e
# ZAP_AUTH_HEADER_VALUE: as imagens oficiais do ZAP mandam este valor no
# cabeçalho Authorization de toda requisição (o token não vai para o log).
docker run --rm --network "$REDE" -v "$SAIDA/zap:/zap/wrk:rw" \
  -e ZAP_AUTH_HEADER_VALUE="Bearer ${TOKEN}" -e ZAP_AUTH_HEADER_SITE="$API" \
  "$ZAP_IMAGE" \
  zap-api-scan.py \
    -t "http://${API}:8000/openapi.json" \
    -f openapi \
    -r zap.html -J zap.json -w zap.md \
    -I
zap=$?
set -e

# --- Schemathesis ------------------------------------------------------------
# Seed fixa: a mesma versão do código gera os mesmos casos, então o resultado
# é reproduzível entre a máquina local e o CI.
echo "== Schemathesis"
set +e
uvx --from "schemathesis==${SCHEMATHESIS_VERSION}" schemathesis \
  --config-file "$(dirname "$0")/schemathesis.toml" run \
  "http://127.0.0.1:${PORTA}/openapi.json" \
  --max-examples "$EXEMPLOS" \
  --seed 20261125 \
  --request-timeout 30 \
  -H "Authorization: Bearer ${TOKEN}" \
  --report junit,html,ndjson \
  --report-dir "$SAIDA/schemathesis"
st=$?
set -e

echo
echo "Resumo DAST (relatórios em $SAIDA):"
echo "  ZAP:          código $zap (0 ok, 1 FAIL, 3 erro)"
echo "  Schemathesis: código $st (0 ok)"
[ "$zap" -eq 0 ] && [ "$st" -eq 0 ]
