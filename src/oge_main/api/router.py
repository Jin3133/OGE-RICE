from fastapi import APIRouter

from oge_main.api.routes import (
    agronomy,
    business_results,
    georeferencing,
    health,
    management_units,
    meta,
    model_pipeline,
    reference_areas,
    task_drafts,
)

api_router = APIRouter()
api_router.include_router(agronomy.router)
api_router.include_router(business_results.router)
api_router.include_router(health.router)
api_router.include_router(meta.router)
api_router.include_router(reference_areas.router)
api_router.include_router(task_drafts.router)
api_router.include_router(management_units.router)
api_router.include_router(georeferencing.router)
api_router.include_router(model_pipeline.router)
