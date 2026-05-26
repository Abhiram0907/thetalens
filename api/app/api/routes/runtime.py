from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.schemas.runtime import RuntimeResponse
from app.services.runtime_info import build_runtime_response

router = APIRouter(prefix="/api", tags=["runtime"])


@router.get("/runtime", response_model=RuntimeResponse)
def runtime(request: Request) -> RuntimeResponse:
    """Active LLM config — disabled in production unless X-Admin-Key is set."""
    settings = get_settings()
    if settings.is_production:
        admin_key = settings.admin_api_key
        provided = request.headers.get("X-Admin-Key", "")
        if not admin_key or provided != admin_key:
            raise HTTPException(status_code=404, detail="Not found")
    return build_runtime_response()
