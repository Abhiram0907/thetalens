from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LlmProvider = Literal["gemini", "ollama"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ThetaLens API"
    cors_origins: str = ""

    # Feature flag — overrides llm.yaml `active` (gemini | ollama)
    llm_active: LlmProvider | None = None
    google_api_key: str = ""

    polygon_api_key: str = ""
    polygon_base_url: str = "https://api.polygon.io"

    finnhub_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
