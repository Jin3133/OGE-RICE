from fastapi import APIRouter

from oge_main.api.contracts import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
def liveness() -> HealthResponse:
    return HealthResponse(status="ok", service="oge-rice-api")


@router.get("/ready", response_model=HealthResponse)
def readiness() -> HealthResponse:
    # Database/provider checks will be added when those dependencies exist.
    return HealthResponse(status="ok", service="oge-rice-api")
