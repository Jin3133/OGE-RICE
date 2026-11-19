from fastapi.testclient import TestClient

from oge_main.api import create_app


def test_recommends_hai_men_growth_stage_without_inventing_stage_quota() -> None:
    response = TestClient(create_app()).get(
        "/api/v1/agronomy/recommendation",
        params={"analysis_date": "2025-07-07", "administrative_code": "320614"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommended_stage"]["code"] == "tillering"
    assert payload["recommended_stage"]["requires_user_confirmation"] is True
    assert payload["stage_quota_status"] == "missing"
    assert payload["seasonal_quotas"][0]["value_m3_per_mu"] == 460.0


def test_rejects_unknown_region() -> None:
    response = TestClient(create_app()).get(
        "/api/v1/agronomy/recommendation",
        params={"analysis_date": "2025-07-07", "administrative_code": "000000"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AGRONOMY_PARAMETERS_NOT_FOUND"
