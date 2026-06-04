from fastapi import HTTPException

from app.config import Settings
from app.core.security import LLM_UNAVAILABLE
from app.llm_config import LlmConfig


def raise_if_llm_unavailable(cfg: LlmConfig, settings: Settings) -> None:
    if cfg.active == "gemini" and not cfg.gemini_api_key_configured():
        detail = LLM_UNAVAILABLE if settings.is_production else cfg.unavailable_detail()
        raise HTTPException(status_code=503, detail=detail)
