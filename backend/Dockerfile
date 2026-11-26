FROM python:3.12-slim

# Aplica as correções de segurança do Debian que saíram depois da imagem base
# (o Trivy no CI bloqueia CVE alta/crítica com correção disponível).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# uv copiado da imagem oficial (versão fixada para o build ser reprodutível)
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /bin/uv

WORKDIR /app

# Instala dependências primeiro: essa camada fica em cache enquanto o lockfile não mudar
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/app ./app
COPY data/processed/medicamentos_sus_canonical.json data/processed/normative_chunks.json data/processed/evidence_chunks_v3.json data/processed/ceaf_live_stock.json data/processed/df_pharmacies_geolocated.json ./data/processed/
ENV APP_DATA_PROCESSED_DIR=/app/data/processed

# Não rodar como root
RUN useradd --create-home appuser
USER appuser

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s \
  CMD python -c "import os, urllib.request; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/health')"

CMD ["sh", "-c", "fastapi run app/main.py --host 0.0.0.0 --port ${PORT:-8000}"]
