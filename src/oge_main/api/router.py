from fastapi import APIRouter

from oge_main.api.routes import health, management_units, meta, reference_areas, task_drafts

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(meta.router)
api_router.include_router(reference_areas.router)
api_router.include_router(task_drafts.router)
api_router.include_router(management_units.router)
