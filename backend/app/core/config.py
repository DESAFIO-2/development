from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações lidas de variáveis de ambiente (ou do arquivo .env)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")

    app_name: str = "SUS Cidadão API"
    environment: str = "local"
    version: str = "0.1.0"


settings = Settings()
