from fastapi import APIRouter

from app.schemas.hello import HelloResponse

router = APIRouter(tags=["hello"])


@router.get("/api/hello", response_model=HelloResponse)
def hello() -> HelloResponse:
    return HelloResponse(message="Hello from FastAPI")
