from pathlib import Path

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

    # RAG & Provedores de IA
    openai_api_key: str = ""
    google_api_key: str = ""
    anthropic_api_key: str = ""

    # Embeddings e Vector Store
    embedding_model_name: str = "BAAI/bge-m3"
    vector_store_path: Path = DATA_DIR / "vectorstore" / "chroma"

    # Diretórios de Dados
    data_raw_dir: Path = DATA_DIR / "raw"
    data_processed_dir: Path = DATA_DIR / "processed"
    data_manifests_dir: Path = DATA_DIR / "manifests"

    # Metas de Qualidade e RAGAS
    rag_faithfulness_threshold: float = 0.92
    rag_top_k: int = 5


settings = Settings()
