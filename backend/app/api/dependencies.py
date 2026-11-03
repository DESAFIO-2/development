from app.core.config import Settings, settings


def get_settings() -> Settings:
    """Provedor de configurações da aplicação para injeção de dependência no FastAPI."""
    return settings
