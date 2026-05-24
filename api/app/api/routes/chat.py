from fastapi import APIRouter, HTTPException

from app.core.dependencies import get_trade_chain
from app.core.disclaimer import DISCLAIMER_STANDARD
from app.llm_config import get_llm_config
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    cfg = get_llm_config()

    if cfg.active == "gemini" and not cfg.gemini_api_key_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini API key missing. Add GOOGLE_API_KEY to api/.env "
                "(get one at https://aistudio.google.com/apikey)."
            ),
        )

    chain = get_trade_chain()
    try:
        reply = await chain.ainvoke({"task": body.message})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=cfg.unavailable_detail()) from exc

    return ChatResponse(reply=reply, model=cfg.resolve_model(), disclaimer=DISCLAIMER_STANDARD)
