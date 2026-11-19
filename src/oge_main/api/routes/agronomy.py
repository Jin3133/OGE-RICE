"""Source-backed crop-calendar and irrigation-parameter recommendations."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query

from oge_main.api.contracts import (
    AgronomyRecommendationResponse,
    GrowthStageRecommendation,
    SeasonalQuotaReference,
)
from oge_main.api.errors import ApiProblem

router = APIRouter(prefix="/agronomy", tags=["agronomy"])


def _parameter_file() -> Path:
    return Path(__file__).resolve().parents[4] / "data" / "reference" / "agronomy" / "haimen-rice-v1.json"


@router.get("/recommendation", response_model=AgronomyRecommendationResponse)
def recommendation(
    analysis_date: Annotated[date, Query()],
    administrative_code: Annotated[str, Query()] = "320614",
) -> AgronomyRecommendationResponse:
    try:
        payload = json.loads(_parameter_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ApiProblem(500, "AGRONOMY_PARAMETERS_INVALID", "agronomy parameters could not be loaded") from error
    if administrative_code != payload["region"]["administrative_code"]:
        raise ApiProblem(404, "AGRONOMY_PARAMETERS_NOT_FOUND", "no agronomy parameters match this region")

    recommended = None
    for item in payload["crop_calendar"]["stages"]:
        start = date.fromisoformat(item["start"])
        end = date.fromisoformat(item["end"])
        # The regional calendar is month/day based; apply it to the requested year.
        start = start.replace(year=analysis_date.year)
        end = end.replace(year=analysis_date.year)
        if start <= analysis_date <= end:
            recommended = GrowthStageRecommendation(
                code=item["code"],
                name=item["name"],
                start=start,
                end=end,
                requires_user_confirmation=True,
            )
            break

    return AgronomyRecommendationResponse(
        parameter_set_id=payload["parameter_set_id"],
        region_name=payload["region"]["name"],
        administrative_code=payload["region"]["administrative_code"],
        irrigation_zone=payload["region"]["irrigation_zone"],
        crop=payload["crop"],
        season=payload["season"],
        analysis_date=analysis_date,
        recommended_stage=recommended,
        stage_evidence_note=payload["crop_calendar"]["evidence_note"],
        seasonal_quotas=[SeasonalQuotaReference.model_validate(item) for item in payload["seasonal_quotas"]],
        stage_quota_status=payload["stage_quota"]["status"],
        stage_quota_message=payload["stage_quota"]["message"],
        sources=payload["sources"],
    )
