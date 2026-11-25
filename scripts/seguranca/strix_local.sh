#!/usr/bin/env bash
# Pentest com Strix na máquina local (pensado para o Mac M4 com Ollama), contra
# o código em ./backend e a API rodando num container efêmero.
# Escopo e triagem: docs/security/pentest_strix.md
#
# Uso (da raiz do repositório):
#   STRIX_LLM=ollama/<modelo> LLM_API_BASE=http://localhost:11434 make strix-local
# Variáveis opcionais:
#   STRIX_MODO=quick          quick | standard | deep
#   STRIX_MAX_BUDGET=5        teto em USD (só faz sentido com provedor pago)
#   STRIX_PORT=8000           porta da API
#   SEG_SEM_BUILD=1           reaproveita a imagem já construída
#   LLM_API_KEY=...           só para provedor externo
set -euo pipefail

STRIX_VERSION="1.7.0"

# shellcheck source=scripts/seguranca/_api.sh
source "$(dirname "$0")/_api.sh"

MODO="${STRIX_MODO:-quick}"
PORTA="${STRIX_PORT:-8000}"
API="sus-cidadao-strix-api"

seg_checar_ferramentas
[ -n "${STRIX_LLM:-}" ] || {
  echo "Defina STRIX_LLM (ex.: STRIX_LLM=ollama/qwen3-vl LLM_API_BASE=http://localhost:11434)." >&2
  exit 1
}
case "$MODO" in quick|standard|deep) ;; *) echo "STRIX_MODO inválido: $MODO" >&2; exit 1 ;; esac

if [[ "$STRIX_LLM" == ollama/* ]]; then
  base="${LLM_API_BASE:-http://localhost:11434}"
  export LLM_API_BASE="$base"
  curl -fsS "$base/api/tags" > /dev/null 2>&1 || {
    echo "Ollama não responde em $base. Rode 'ollama serve' antes." >&2
    exit 1
  }
fi

# Telemetria do Strix desligada: nada sai da máquina além do que o LLM recebe.
export STRIX_TELEMETRY=0

# O sandbox do Strix chega na API por host.docker.internal. No Docker Desktop
# (macOS) isso alcança o 127.0.0.1 do host; no Linux, só o gateway da bridge.
# Em nenhum caso a API fica exposta na rede local.
if [ "$(uname -s)" = "Darwin" ]; then
  IP_BIND="127.0.0.1"
else
  IP_BIND="$(docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}')"
fi

mkdir -p output/strix
# O Strix monta o alvo com escrita: os agentes recebem uma cópia do backend
# commitado (HEAD), nunca a pasta de trabalho. Alterações não commitadas
# ficam de fora do scan.
COPIA="$(mktemp -d "${TMPDIR:-/tmp}/strix-alvo.XXXXXX")"
git archive HEAD backend | tar -x -C "$COPIA"
trap 'api_derrubar "$API" output/strix/api.log; rm -rf "$COPIA"' EXIT

api_build
api_subir "$API" "$IP_BIND" "$PORTA"

args=(
  -n
  -t "$COPIA/backend"
  -t "http://localhost:${PORTA}"
  --scan-mode "$MODO"
  --scope-mode full
  --fail-on high
  --instruction-file .github/strix/instrucoes.md
)
[ -n "${STRIX_MAX_BUDGET:-}" ] && args+=(--max-budget "$STRIX_MAX_BUDGET")

echo "== Strix ${STRIX_VERSION} (${STRIX_LLM}, modo ${MODO})"
set +e
uvx --python 3.12 --from "strix-agent==${STRIX_VERSION}" strix "${args[@]}" 2>&1 | tee output/strix/strix_saida.log
codigo=${PIPESTATUS[0]}
set -e

echo
echo "Relatório em strix_runs/ e saída em output/strix/. Código do Strix: $codigo"
echo "(0 sem achados altos/críticos, 2 com achados, outro = falha)"
exit "$codigo"
