"""Run the minimum cropland-area to irrigation-demand business cycle."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import rasterio

SQUARE_METRES_PER_MU = 2000 / 3


def _measure_candidate_area(mask_path: str | Path) -> tuple[float, dict[str, Any]]:
    with rasterio.open(mask_path) as source:
        mask = source.read(1) > 0
        pixel_area = abs(source.transform.a * source.transform.e)
        area_m2 = float(mask.sum() * pixel_area)
        metadata = {
            "raster_path": str(Path(mask_path).resolve()),
            "crs": str(source.crs),
            "pixel_size_metres": [abs(source.transform.a), abs(source.transform.e)],
            "candidate_pixel_count": int(mask.sum()),
        }
    return area_m2, metadata


def _attention_level(share: float) -> str:
    if share >= 0.35:
        return "high"
    if share >= 0.2:
        return "medium"
    return "low"


def run_assessment(task: dict[str, Any]) -> dict[str, Any]:
    """Calculate candidate area, stage demand and attention level for every unit."""
    stage = task["growth_stage"]
    quota = float(task["irrigation_quota_m3_per_mu"])
    results: list[dict[str, Any]] = []
    total_demand = 0.0
    for unit in task["management_units"]:
        measured_area_m2, raster_metadata = _measure_candidate_area(
            unit["candidate_mask_path"]
        )
        override = unit.get("area_override_m2")
        area_m2 = float(override) if override is not None else measured_area_m2
        area_mu = area_m2 / SQUARE_METRES_PER_MU
        demand_m3 = area_mu * quota
        total_demand += demand_m3
        results.append(
            {
                "unit_id": unit["unit_id"],
                "unit_name": unit["unit_name"],
                "candidate_area_m2": round(area_m2, 2),
                "candidate_area_mu": round(area_mu, 2),
                "growth_stage": stage,
                "irrigation_quota_m3_per_mu": quota,
                "reference_irrigation_demand_m3": round(demand_m3, 2),
                "area_source": "user_override" if override is not None else "candidate_mask",
                "remote_sensing_evidence": raster_metadata,
            }
        )
    for result in results:
        share = (
            result["reference_irrigation_demand_m3"] / total_demand
            if total_demand
            else 0.0
        )
        result["demand_share"] = round(share, 6)
        result["attention_level"] = _attention_level(share)
        result["quality_statement"] = task["quality_statement"]

    return {
        "task_id": task["task_id"],
        "result_version": int(task.get("result_version", 1)),
        "parent_result_version": task.get("parent_result_version"),
        "feedback": task.get("feedback"),
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "completed",
        "business_scope": task["business_scope"],
        "crop_type": task["crop_type"],
        "model_target": "cultivated_land_candidate",
        "growth_stage": stage,
        "calculation_formula": "W = A_mu * M_m3_per_mu",
        "total_candidate_area_mu": round(
            sum(item["candidate_area_mu"] for item in results), 2
        ),
        "total_reference_irrigation_demand_m3": round(total_demand, 2),
        "units": results,
        "limitations": [
            "Candidate masks do not independently identify rice or other crop types.",
            "Reference irrigation demand is not actual withdrawal or supply.",
            "Attention levels are relative within this demonstration task.",
        ],
    }
