from fastapi import APIRouter

from app.schemas.runtime import RuntimeResponse
from app.services.runtime_info import build_runtime_response

router = APIRouter(prefix="/api", tags=["runtime"])


@router.get("/runtime", response_model=RuntimeResponse)
def runtime() -> RuntimeResponse:
    """Active LLM feature flag, resolved model, and full llm.yaml snapshot."""
    return build_runtime_response()
