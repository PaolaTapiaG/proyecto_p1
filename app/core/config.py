from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Lumora Roleplay API"
    app_env: str = "local"
    app_debug: bool = False
    database_url: str = "postgresql+psycopg://postgres:change-me@127.0.0.1:5432/Lumora"
    auto_create_tables: bool = False

    redis_url: str | None = None

    ai_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_api_key: str | None = None
    ollama_chat_model: str = "qwen3:8b"
    ollama_embedding_model: str = "qwen3-embedding:0.6b"
    ollama_embedding_dimensions: int = 1024
    # El roleplay prioriza respuesta inmediata. Las tareas de razonamiento lo activan al pedirlo.
    ollama_think: bool = False
    ollama_keep_alive: str = "10m"
    ollama_context_window: int = 8192
    ollama_max_output_tokens: int = 1600
    character_research_enabled: bool = True
    character_research_timeout_seconds: int = 15
    local_media_root: str = "storage/uploads"
    max_upload_bytes: int = 6 * 1024 * 1024
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"

    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_jwt_secret: str | None = None
    supabase_storage_bucket: str = "bot-assets"
    allow_dev_auth: bool = True
    allow_local_auth: bool = True
    local_jwt_secret: str = "lumora-local-development-secret-change-me"
    local_token_minutes: int = 60 * 24 * 7
    discord_support_url: str | None = None

    cors_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
    )
    trusted_hosts_raw: str = Field(default="localhost,127.0.0.1", validation_alias="TRUSTED_HOSTS")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_postgres_driver(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return "postgresql+psycopg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.casefold() == "production"

    @property
    def trusted_hosts(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts_raw.split(",") if host.strip()]

    def validate_production(self) -> None:
        if not self.is_production:
            return
        errors: list[str] = []
        if self.allow_dev_auth:
            errors.append("ALLOW_DEV_AUTH must be false")
        if self.auto_create_tables:
            errors.append("AUTO_CREATE_TABLES must be false; run Alembic migrations")
        if self.local_jwt_secret == "lumora-local-development-secret-change-me":
            errors.append("LOCAL_JWT_SECRET must be replaced")
        if "change-me" in self.database_url:
            errors.append("DATABASE_URL must use a real production credential")
        if not self.redis_url:
            errors.append("REDIS_URL is required")
        if self.ai_provider == "ollama_cloud" and not self.ollama_api_key:
            errors.append("OLLAMA_API_KEY is required for Ollama Cloud")
        if "*" in self.cors_origins:
            errors.append("CORS_ORIGINS cannot contain a wildcard")
        if not self.trusted_hosts or any(host in {"localhost", "127.0.0.1"} for host in self.trusted_hosts):
            errors.append("TRUSTED_HOSTS must contain the production domain")
        if errors:
            raise RuntimeError("Invalid production configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
