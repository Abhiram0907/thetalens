import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.services.runtime_info import build_runtime_response
from app.tools.providers import get_finnhub_client

logger = logging.getLogger("thetalens")

load_dotenv()


def create_app() -> FastAPI:
    settings = get_settings()
    rt = build_runtime_response()
    logger.info(
        "LLM active=%s alias=%s → %s (temp=%s, api_key=%s) [all chains]",
        rt.active,
        rt.alias,
        rt.model,
        rt.temperature,
        rt.api_key_configured,
    )

    if settings.finnhub_api_key:
        get_finnhub_client(settings.finnhub_api_key)
        logger.info("Finnhub client initialized (peers, news, earnings)")
    else:
        logger.warning("FINNHUB_API_KEY not set — using Polygon fallback for news/earnings")

    app = FastAPI(title=settings.app_name)
    app.include_router(api_router)

    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    if settings.cors_origins:
        origins.extend(
            o.strip() for o in settings.cors_origins.split(",") if o.strip()
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()
