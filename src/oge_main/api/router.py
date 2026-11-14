from fastapi import APIRouter

from oge_main.api.routes import health, meta

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meta.router)
