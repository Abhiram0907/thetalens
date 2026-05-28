import logging

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.core.logging_config import configure_logging
from app.core.security import GENERIC_ERROR, redact_secrets
from app.middleware.rate_limit import limiter
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.services.runtime_info import build_runtime_response
from app.tools.providers import get_finnhub_client

logger = logging.getLogger("thetalens")

load_dotenv()
configure_logging()


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_production()

    rt = build_runtime_response()
    logger.info(
        "LLM active=%s alias=%s → %s (temp=%s, api_key=%s, env=%s) [all chains]",
        rt.active,
        rt.alias,
        rt.model,
        rt.temperature,
        rt.api_key_configured,
        settings.app_env,
    )

    if settings.finnhub_api_key:
        get_finnhub_client(settings.finnhub_api_key)
        logger.info("Finnhub client initialized (peers, news, earnings)")
    else:
        logger.warning(
            "FINNHUB_API_KEY not set — peers/earnings/sentiment degraded "
            "(Polygon news heuristics where applicable)"
        )

    app = FastAPI(
        title=settings.app_name,
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.limiter = limiter
    app.state.settings = settings
    app.include_router(api_router)

    if settings.is_production:
        origins = settings.production_origins()
        allow_origin_regex = settings.vercel_preview_origin_regex or None
        allow_credentials = False
    else:
        origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
        if settings.cors_origins:
            origins.extend(settings.production_origins())
        allow_origin_regex = None
        allow_credentials = True

    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=allow_origin_regex,
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "X-Admin-Key"],
    )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        logger.exception("Unhandled error on %s", request.url.path)
        detail = GENERIC_ERROR if settings.is_production else redact_secrets(str(exc))
        return JSONResponse(status_code=500, content={"detail": detail})

    return app


app = create_app()
