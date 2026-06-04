"""Export research reports as HTML or JSON."""

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from app.middleware.rate_limit import limiter
from app.middleware.rate_limits import EXPORT
from app.schemas.export import ExportRequest
from app.schemas.research_report import ResearchReport
from app.services.export_html import render_research_report_html
from app.services.research_report import build_research_report
from app.services.research_report_build import ensure_report_market_intel

router = APIRouter(prefix="/api/export", tags=["export"])


def _resolve_report(body: ExportRequest) -> ResearchReport:
    if body.research_report is not None:
        return body.research_report
    if not body.strategies:
        raise HTTPException(
            status_code=400,
            detail="Nothing to export — run analysis first or include strategies in the payload.",
        )
    return build_research_report(
        parsed_view=body.parsed_view,
        strategies=body.strategies,
        reasoning_steps=body.reasoning_steps,
        underlying_price=body.underlying_price,
        data_provenance=body.data_provenance,
        query=body.query,
        captured=body.captured,
        enriched_context=body.enriched_context,
    )


def _filename(report: ResearchReport, ext: str) -> str:
    ticker = report.parsed_view.underlying or "report"
    date = report.generated_at.strftime("%Y%m%d")
    return f"thetalens-{ticker.lower()}-{date}.{ext}"


@router.post("")
@limiter.limit(EXPORT)
async def export_research(
    request: Request,
    body: Annotated[ExportRequest, Body()],
) -> Response:
    report = await ensure_report_market_intel(
        _resolve_report(body),
        body.enriched_context,
    )

    if body.format == "json":
        return JSONResponse(
            content=report.model_dump(mode="json"),
            headers={
                "Content-Disposition": f'attachment; filename="{_filename(report, "json")}"',
            },
        )

    html_doc = render_research_report_html(report)
    return HTMLResponse(
        content=html_doc,
        headers={
            "Content-Disposition": f'attachment; filename="{_filename(report, "html")}"',
        },
    )
