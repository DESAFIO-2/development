from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


class Settings(BaseSettings):
    """Configurações lidas de variáveis de ambiente (ou do arquivo .env)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        extra="ignore",
    )

    app_name: str = "SUS Cidadão API"
    environment: str = "local"
    version: str = "0.1.0"
    log_level: str = "INFO"

    # RAG & Provedores de IA
    llm_provider: str = "gemini"
    llm_model_name: str = ""
    ollama_base_url: str = "http://localhost:11434"
    google_api_key: str = ""

    # Ativação explícita, independente dos experimentos da Semana 3.
    agents_provider: Literal["deterministic", "ollama", "gemini"] = "deterministic"
    agents_model: str = "qwen2.5:7b"
    agents_timeout_seconds: float = Field(default=60.0, gt=0, le=120)

    # Diretório de Dados Processados
    data_processed_dir: Path = DATA_DIR / "processed"


settings = Settings()
