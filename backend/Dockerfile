FROM python:3.12-slim

# uv copiado da imagem oficial (versão fixada para o build ser reprodutível)
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /bin/uv

WORKDIR /app

# Instala dependências primeiro: essa camada fica em cache enquanto o lockfile não mudar
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY backend/app ./app
COPY data/processed/medicamentos_sus_canonical.json data/processed/normative_chunks.json ./data/processed/
ENV APP_DATA_PROCESSED_DIR=/app/data/processed

# Não rodar como root
RUN useradd --create-home appuser
USER appuser

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["fastapi", "run", "app/main.py", "--port", "8000"]
