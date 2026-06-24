from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"

    d1_database_id: str
    d1_api_token: str
    d1_account_id: str

    log_level: str = "INFO"

    hrms_sync_interval_minutes: int = 60

    schema_cache_ttl_seconds: int = 300
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    groq_model: str = "llama-3.1-8b-instant"
    groq_max_tokens: int = 300
    groq_temperature: float = 0.0
    enable_langgraph: bool = Field(default=False, validation_alias="ENABLE_LANGGRAPH")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()