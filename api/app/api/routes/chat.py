from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request

from app.config import get_settings
from app.core.dependencies import get_trade_chain
from app.core.disclaimer import DISCLAIMER_STANDARD
from app.core.security import LLM_UNAVAILABLE
from app.llm_config import get_llm_config
from app.middleware.rate_limit import limiter
from app.middleware.rate_limits import CHAT
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(CHAT)
async def chat(
    request: Request,
    body: Annotated[ChatRequest, Body()],
) -> ChatResponse:
    cfg = get_llm_config()
    settings = get_settings()

    if cfg.active == "gemini" and not cfg.gemini_api_key_configured():
        raise HTTPException(
            status_code=503,
            detail=LLM_UNAVAILABLE if settings.is_production else cfg.unavailable_detail(),
        )

    chain = get_trade_chain()
    try:
        reply = await chain.ainvoke({"task": body.message})
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=LLM_UNAVAILABLE if settings.is_production else cfg.unavailable_detail(),
        ) from exc

    return ChatResponse(reply=reply, model=cfg.resolve_model(), disclaimer=DISCLAIMER_STANDARD)
