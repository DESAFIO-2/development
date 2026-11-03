# SUS Cidadão — Backend

API em FastAPI do SUS Cidadão (Challenge 2 - Residência em IA UnB).

## Requisitos

- [uv](https://docs.astral.sh/uv/) (instala o Python 3.12 sozinho)
- Docker (opcional, para rodar a imagem)

## Rodar localmente

```bash
cd backend
uv sync
cp .env.example .env   # ajuste se precisar
uv run fastapi dev app/main.py
```

Swagger em http://localhost:8000/docs e healthcheck em http://localhost:8000/health.

## Checagens (as mesmas do CI)

```bash
uv run ruff format .
uv run ruff check .
uv run mypy app tests
uv run pytest
```

## Docker

```bash
docker build -t sus-cidadao-backend .
docker run --rm -p 8000:8000 sus-cidadao-backend
```

## Configuração

Variáveis de ambiente com prefixo `APP_` (veja `.env.example`):

| Variável          | Padrão            |
| ----------------- | ----------------- |
| `APP_APP_NAME`    | `SUS Cidadão API` |
| `APP_ENVIRONMENT` | `local`           |
| `APP_VERSION`     | `0.1.0`           |
