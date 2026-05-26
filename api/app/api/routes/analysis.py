from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request

from app.config import get_settings
from app.core.security import LLM_UNAVAILABLE
from app.llm_config import get_llm_config
from app.middleware.rate_limit import limiter
from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse, IntentRequest, IntentResponse
from app.services.analysis import run_analysis
from app.services.intent import evaluate_intent

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/intent", response_model=IntentResponse)
@limiter.limit("30/minute")
async def parse_intent(
    request: Request,
    body: Annotated[IntentRequest, Body()],
) -> IntentResponse:
    cfg = get_llm_config()
    settings = get_settings()
    try:
        return await evaluate_intent(body.query)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=LLM_UNAVAILABLE if settings.is_production else cfg.unavailable_detail(),
        ) from exc


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit("20/minute")
async def analyze(
    request: Request,
    body: Annotated[AnalyzeRequest, Body()],
) -> AnalyzeResponse:
    return await run_analysis(body.query)
