from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações globais da aplicação SUS Cidadão."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Identificação do Projeto
    PROJECT_NAME: str = "SUS Cidadão (NavegaSUS)"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Servidores
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    UI_PORT: int = 8501

    # Provedores de LLM
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Embeddings & Vetores
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-m3"
    VECTOR_STORE_PATH: Path = Path("./data/vectorstore/chroma")

    # Diretórios de Dados
    DATA_RAW_DIR: Path = Path("./data/raw")
    DATA_STAGING_DIR: Path = Path("./data/staging")
    DATA_PROCESSED_DIR: Path = Path("./data/processed")
    DATA_MANIFESTS_DIR: Path = Path("./data/manifests")

    # Guardrails & RAG
    RAG_FAITHFULNESS_THRESHOLD: float = 0.92
    RAG_TOP_K: int = 5


settings = Settings()
