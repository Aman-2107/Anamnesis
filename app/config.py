# app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = Field(..., validation_alias="DATABASE_URL")
    embedding_dim: int = Field(384, validation_alias="EMBEDDING_DIM")

    openai_api_key: str | None = Field(None, validation_alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(None, validation_alias="OPENAI_BASE_URL")
    llm_model: str = Field("llama-3.3-70b-versatile", validation_alias="LLM_MODEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
