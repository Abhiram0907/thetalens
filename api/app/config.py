from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LlmProvider = Literal["gemini", "ollama"]

# Only ThetaLens Vercel preview deployments (not arbitrary *.vercel.app projects).
DEFAULT_VERCEL_PREVIEW_REGEX = r"https://thetalens[a-z0-9-]*\.vercel\.app"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ThetaLens API"
    app_env: str = "development"
    cors_origins: str = ""
    vercel_preview_origin_regex: str = DEFAULT_VERCEL_PREVIEW_REGEX

    # Optional: protects /api/runtime in production (X-Admin-Key header).
    admin_api_key: str = ""

    # Feature flag — overrides llm.yaml `active` (gemini | ollama)
    llm_active: LlmProvider | None = None
    google_api_key: str = ""

    polygon_api_key: str = ""
    polygon_base_url: str = "https://api.polygon.io"

    finnhub_api_key: str = ""

    @field_validator("app_env")
    @classmethod
    def normalize_env(cls, value: str) -> str:
        return value.strip().lower()

    @property
    def is_production(self) -> bool:
        if self.app_env in ("production", "prod"):
            return True
        # Render sets CORS_ORIGINS in production even if APP_ENV is unset.
        return bool(self.cors_origins.strip())

    def production_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_production(self) -> None:
        """Fail fast at startup when required production secrets are missing."""
        if not self.is_production:
            return
        missing: list[str] = []
        if not self.google_api_key:
            missing.append("GOOGLE_API_KEY")
        if not self.polygon_api_key:
            missing.append("POLYGON_API_KEY")
        if not self.cors_origins.strip():
            missing.append("CORS_ORIGINS")
        if missing:
            raise RuntimeError(
                "Missing required production environment variables: "
                + ", ".join(missing)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
