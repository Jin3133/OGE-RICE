from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from oge_main.api import create_app


def result_payload() -> dict:
    return {
        "task_id": "yuelai-test-v1",
        "result_version": 1,
        "parent_result_version": None,
        "feedback": None,
        "generated_at": "2026-11-19T06:30:00+00:00",
        "status": "completed",
        "business_scope": "悦来测试范围",
        "crop_type": "rice",
        "model_target": "cultivated_land_candidate",
        "growth_stage": "tillering",
        "calculation_formula": "W = A_mu * M_m3_per_mu",
        "total_candidate_area_mu": 100.0,
        "total_reference_irrigation_demand_m3": 8000.0,
        "units": [
            {
                "unit_id": "unit-yuelai",
                "unit_name": "悦来灌区",
                "candidate_area_m2": 66666.67,
                "candidate_area_mu": 100.0,
                "growth_stage": "tillering",
                "irrigation_quota_m3_per_mu": 80.0,
                "reference_irrigation_demand_m3": 8000.0,
                "area_source": "candidate_mask",
                "remote_sensing_evidence": {"crs": "EPSG:32651"},
                "demand_share": 1.0,
                "attention_level": "high",
                "quality_statement": "测试成果",
            }
        ],
        "limitations": ["test limitation"],
    }


def test_lists_and_reads_versioned_business_result(tmp_path: Path, monkeypatch) -> None:
    result_directory = tmp_path / "yuelai-v1"
    result_directory.mkdir()
    (result_directory / "demand-result.json").write_text(
        json.dumps(result_payload()), encoding="utf-8"
    )
    monkeypatch.setenv("OGE_BUSINESS_RESULTS_DIR", str(tmp_path))
    client = TestClient(create_app())

    collection = client.get("/api/v1/business-results")
    detail = client.get("/api/v1/business-results/yuelai-test-v1")

    assert collection.status_code == 200
    assert collection.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["total_reference_irrigation_demand_m3"] == 8000.0


def test_missing_business_result_returns_stable_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OGE_BUSINESS_RESULTS_DIR", str(tmp_path))
    response = TestClient(create_app()).get("/api/v1/business-results/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "BUSINESS_RESULT_NOT_FOUND"
