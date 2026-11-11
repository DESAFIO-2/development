from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    openai_api_key: str = ""
    google_api_key: str = ""
    anthropic_api_key: str = ""

    # Embeddings e Vector Store
    embedding_model_name: str = "BAAI/bge-m3"
    vector_store_path: Path = Path("../data/vectorstore/chroma")

    # Diretórios de Dados
    data_raw_dir: Path = Path("../data/raw")
    data_processed_dir: Path = Path("../data/processed")
    data_manifests_dir: Path = Path("../data/manifests")

    # Metas de Qualidade e RAGAS
    rag_faithfulness_threshold: float = 0.92
    rag_top_k: int = 5


settings = Settings()
