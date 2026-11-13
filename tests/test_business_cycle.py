from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from oge_main.business import run_assessment


def test_business_cycle_calculates_area_demand_and_level(tmp_path: Path) -> None:
    mask_path = tmp_path / "mask.tif"
    mask = np.array([[1, 1], [0, 0]], dtype=np.uint8)
    with rasterio.open(
        mask_path,
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype="uint8",
        crs="EPSG:32650",
        transform=from_origin(0, 20, 10, 10),
    ) as target:
        target.write(mask, 1)
    result = run_assessment(
        {
            "task_id": "test",
            "business_scope": "test scope",
            "crop_type": "rice",
            "growth_stage": "tillering",
            "irrigation_quota_m3_per_mu": 100,
            "quality_statement": "test quality",
            "management_units": [
                {
                    "unit_id": "u1",
                    "unit_name": "unit 1",
                    "candidate_mask_path": str(mask_path),
                }
            ],
        }
    )
    assert result["total_candidate_area_mu"] == 0.3
    assert result["total_reference_irrigation_demand_m3"] == 30.0
    assert result["units"][0]["attention_level"] == "high"
