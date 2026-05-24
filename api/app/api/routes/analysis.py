from fastapi import APIRouter, HTTPException

from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse, IntentRequest, IntentResponse
from app.services.analysis import run_analysis
from app.services.intent import evaluate_intent
from app.llm_config import get_llm_config

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/intent", response_model=IntentResponse)
async def parse_intent(body: IntentRequest) -> IntentResponse:
    cfg = get_llm_config()
    try:
        return await evaluate_intent(body.query)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=cfg.unavailable_detail()) from exc


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    return await run_analysis(body.query)
