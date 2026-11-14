from fastapi.testclient import TestClient

from oge_main.api import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_health_and_metadata_are_versioned() -> None:
    response = client().get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "oge-rice-api"}
    assert response.headers["Request-Id"]

    metadata = client().get("/api/v1/meta")
    assert metadata.status_code == 200
    assert metadata.json()["result_modes"] == ["illustrative"]


def test_request_id_is_preserved() -> None:
    response = client().get(
        "/api/v1/health/live", headers={"Request-Id": "request-test-001"}
    )
    assert response.headers["Request-Id"] == "request-test-001"


def test_invalid_request_id_is_replaced() -> None:
    response = client().get(
        "/api/v1/health/live", headers={"Request-Id": "invalid value with spaces"}
    )
    assert response.headers["Request-Id"] != "invalid value with spaces"


def test_not_found_uses_stable_error_contract() -> None:
    response = client().get("/api/v1/does-not-exist")
    assert response.status_code == 404
    payload = response.json()["error"]
    assert payload["code"] == "RESOURCE_NOT_FOUND"
    assert payload["request_id"] == response.headers["Request-Id"]


def test_openapi_operation_ids_are_unique_and_stable() -> None:
    schema = client().get("/api/v1/openapi.json").json()
    operation_ids = [
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
    ]
    assert len(operation_ids) == len(set(operation_ids))
    assert "health-liveness" in operation_ids
    assert "meta-metadata" in operation_ids
