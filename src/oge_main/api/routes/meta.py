from fastapi import APIRouter

from oge_main.api.contracts import ApiMetadata

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("", response_model=ApiMetadata)
def metadata() -> ApiMetadata:
    return ApiMetadata(
        service="oge-rice-api",
        api_version="v1",
        result_modes=["illustrative"],
        documentation="/api/v1/docs",
    )
