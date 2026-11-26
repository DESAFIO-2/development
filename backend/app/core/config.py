from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
    # Padrão offline/determinístico; local validado com Ollama `qwen3.5:4b`.
    # Mantém GeminiRESTGeneratorAdapter plugável via APP_AGENTS_PROVIDER=gemini.
    agents_provider: Literal["deterministic", "ollama", "gemini"] = "deterministic"
    agents_model: str = "qwen3.5:4b"
    agents_timeout_seconds: float = Field(default=60.0, gt=0, le=120)

    # Multimodalidade Semana 5 (STT desabilitado por padrão até ativação explícita)
    stt_provider: Literal["disabled", "faster_whisper", "whisper_http"] = "disabled"
    stt_model: str = "small"
    stt_base_url: str = "http://localhost:8001"
    stt_timeout_seconds: float = Field(default=30.0, gt=0, le=120)

    # Diretório de Dados Processados
    data_processed_dir: Path = DATA_DIR / "processed"

    # Origens permitidas para clientes Web (Expo Web / browser). Vazio desabilita CORS.
    cors_origins: str = "http://localhost:8081,http://127.0.0.1:8081"

    # --- Proteções da API ---------------------------------------------------
    # `None` = automático: rígido em qualquer ambiente que não seja "local".
    # No local, testes, DAST e evals seguem rodando sem token nem limite.
    expor_docs: bool | None = None
    rate_limit_ativo: bool | None = None
    # Requisições por minuto, por IP, em cada grupo de rotas.
    rate_limit_geral_por_minuto: int = Field(default=120, ge=1)
    rate_limit_pesado_por_minuto: int = Field(default=20, ge=1)
    rate_limit_auth_por_minuto: int = Field(default=5, ge=1)
    # Teto do corpo das rotas JSON (o multimodal tem teto próprio, maior).
    max_corpo_json_bytes: int = Field(default=64 * 1024, ge=1024)

    # --- Autenticação ---------------------------------------------------------
    # `None` = obrigatória em qualquer ambiente que não seja "local".
    auth_obrigatoria: bool | None = None
    # Banco de usuários. Vazio no local = repositório em memória (some ao reiniciar).
    # Ex.: postgresql://remedia:<senha>@127.0.0.1:5432/remedia
    database_url: SecretStr = SecretStr("")
    # Chave HS256 dos tokens de acesso (>= 32 bytes). Vazia só no local, onde
    # cada subida gera uma aleatória (os tokens antigos deixam de valer).
    auth_jwt_secret: SecretStr = SecretStr("")
    # "Pimenta" do HMAC do CPF: o banco nunca guarda o CPF em texto puro.
    # Trocar esta chave invalida todos os cadastros; guarde-a como a do JWT.
    auth_cpf_pepper: SecretStr = SecretStr("")
    auth_issuer: str = "remedia-api"
    auth_audience: str = "remedia-app"
    auth_access_ttl_min: int = Field(default=15, ge=1, le=60)
    auth_refresh_ttl_dias: int = Field(default=30, ge=1, le=90)
    auth_max_tentativas: int = Field(default=5, ge=1, le=20)
    auth_bloqueio_min: int = Field(default=15, ge=1, le=1440)

    @property
    def auth_exigida(self) -> bool:
        return not self.ambiente_local if self.auth_obrigatoria is None else self.auth_obrigatoria

    @property
    def ambiente_local(self) -> bool:
        return self.environment.strip().lower() == "local"

    @property
    def docs_expostos(self) -> bool:
        return self.ambiente_local if self.expor_docs is None else self.expor_docs

    @property
    def rate_limit_ligado(self) -> bool:
        return not self.ambiente_local if self.rate_limit_ativo is None else self.rate_limit_ativo

    @property
    def cors_origins_list(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                origin.strip().rstrip("/")
                for origin in self.cors_origins.split(",")
                if origin.strip()
            )
        )


settings = Settings()
