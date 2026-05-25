"""Scanner endpoint: find stocks with similar movement to a seed ticker."""

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.security import UPSTREAM_UNAVAILABLE, safe_client_message
from app.middleware.rate_limit import limiter
from app.services.scanner import ScannerStock, SeedContext, scan_similar
from app.tools.registry import PolygonClient

router = APIRouter(prefix="/api/scanner", tags=["scanner"])


class ScannerRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=5, description="Seed ticker symbol")


class ScannerResponse(BaseModel):
    seed: str
    seed_context: SeedContext
    results: list[ScannerStock]


def _get_polygon_client() -> PolygonClient:
    settings = get_settings()
    if not settings.polygon_api_key:
        raise HTTPException(503, "POLYGON_API_KEY not configured")
    return PolygonClient(api_key=settings.polygon_api_key, base_url=settings.polygon_base_url)


@router.post("", response_model=ScannerResponse)
@limiter.limit("20/minute")
async def scan_stocks(
    request: Request,
    req: Annotated[ScannerRequest, Body()],
):
    ticker = req.ticker.upper().strip()
    polygon = _get_polygon_client()
    settings = get_settings()
    try:
        seed_ctx, results = await scan_similar(ticker, polygon, top_n=5)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=safe_client_message(
                exc,
                default=UPSTREAM_UNAVAILABLE,
                dev_detail=not settings.is_production,
            ),
        ) from exc

    return ScannerResponse(seed=ticker, seed_context=seed_ctx, results=results)
