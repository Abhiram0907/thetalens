from fastapi import APIRouter

from app.api.routes import agent, analysis, export, health, runtime, scanner

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(runtime.router)
api_router.include_router(analysis.router)
api_router.include_router(agent.router)
api_router.include_router(scanner.router)
api_router.include_router(export.router)
