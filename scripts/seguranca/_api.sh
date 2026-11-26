# shellcheck shell=bash
# Funções comuns para subir a API do backend num container efêmero.
# Usado por dast.sh e strix_local.sh (via `source`), não é executado sozinho.

API_IMAGEM="sus-cidadao-backend:seguranca"

api_build() {
  if [ "${SEG_SEM_BUILD:-0}" != "1" ]; then
    docker build -t "$API_IMAGEM" -f backend/Dockerfile .
  fi
}

# Variáveis de ambiente extras para o container (ex.: login obrigatório no DAST).
# Cada item no formato do docker: (-e NOME=valor -e OUTRO=valor).
API_ENV_EXTRA=()

# api_subir <nome> <ip_bind> <porta> [rede]
# Modo determinístico e STT desligado (padrão): nenhuma chamada sai da API.
api_subir() {
  local nome="$1" ip="$2" porta="$3" rede="${4:-}"
  local args=(-d --name "$nome" -p "${ip}:${porta}:8000" -e APP_AGENTS_PROVIDER=deterministic)
  [ -n "$rede" ] && args+=(--network "$rede")
  [ "${#API_ENV_EXTRA[@]}" -gt 0 ] && args+=("${API_ENV_EXTRA[@]}")
  docker rm -f "$nome" > /dev/null 2>&1 || true
  docker run "${args[@]}" "$API_IMAGEM" > /dev/null

  echo "Aguardando a API em http://${ip}:${porta}/health ..."
  for _ in $(seq 1 30); do
    if curl -fsS "http://${ip}:${porta}/health" > /dev/null 2>&1; then return 0; fi
    sleep 2
  done
  docker logs "$nome" >&2 || true
  echo "API não subiu." >&2
  return 1
}

# api_token <url_base>
# Cadastra um usuário sintético na API efêmera (repositório em memória, some com
# o container) e imprime o access token. CPF de teste com dígitos válidos; senha
# aleatória a cada execução.
api_token() {
  local base="$1" senha
  senha="dast-$(od -An -N12 -tx1 /dev/urandom | tr -d ' \n')"
  curl -fsS -X POST "${base}/api/v1/auth/cadastro" \
    -H 'Content-Type: application/json' \
    -d "{\"cpf\": \"529.982.247-25\", \"senha\": \"${senha}\"}" \
    | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])'
}

# api_derrubar <nome> <arquivo_log>
api_derrubar() {
  docker logs "$1" > "$2" 2>&1 || true
  docker rm -f "$1" > /dev/null 2>&1 || true
}

seg_checar_ferramentas() {
  [ -f backend/Dockerfile ] || { echo "Rode da raiz do repositório." >&2; exit 1; }
  command -v docker > /dev/null || { echo "Docker não encontrado." >&2; exit 1; }
  docker info > /dev/null 2>&1 || { echo "Docker não está rodando." >&2; exit 1; }
  command -v uvx > /dev/null || { echo "uv não encontrado (https://docs.astral.sh/uv/)." >&2; exit 1; }
}
