"""Scanner endpoint: find stocks with similar movement to a seed ticker."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
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
    key = settings.polygon_api_key or os.environ.get("POLYGON_API_KEY", "")
    if not key:
        raise HTTPException(503, "POLYGON_API_KEY not configured")
    return PolygonClient(api_key=key, base_url=settings.polygon_base_url)


@router.post("", response_model=ScannerResponse)
async def scan_stocks(req: ScannerRequest):
    ticker = req.ticker.upper().strip()
    polygon = _get_polygon_client()
    try:
        seed_ctx, results = await scan_similar(ticker, polygon, top_n=5)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Scanner error: {exc}") from exc

    return ScannerResponse(seed=ticker, seed_context=seed_ctx, results=results)
