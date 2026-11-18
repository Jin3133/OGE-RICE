from __future__ import annotations

from fastapi.testclient import TestClient
from rasterio.warp import transform

from oge_main.api import create_app


def target(x: float, y: float) -> tuple[float, float]:
    easting = 350_000.0 + 1.4 * x + 0.08 * y
    northing = 3_535_000.0 - 0.03 * x - 1.35 * y
    longitude, latitude = transform("EPSG:32651", "EPSG:4326", [easting], [northing])
    return longitude[0], latitude[0]


def payload() -> dict:
    pixel_points = [(100, 100), (7000, 200), (200, 8000), (7200, 8200), (4000, 4500)]
    return {
        "image_id": "yuelai-irrigation-district",
        "image_width": 8056,
        "image_height": 9111,
        "projected_crs": "EPSG:32651",
        "control_points": [
            {
                "point_id": f"gcp-{index + 1}",
                "pixel_x": x,
                "pixel_y": y,
                "longitude": target(x, y)[0],
                "latitude": target(x, y)[1],
            }
            for index, (x, y) in enumerate(pixel_points)
        ],
        "pixel_boundary": {
            "type": "Polygon",
            "coordinates": [[[100, 100], [7000, 200], [7200, 8200], [200, 8000], [100, 100]]],
        },
    }


def test_fit_endpoint_returns_report_and_wgs84_boundary() -> None:
    response = TestClient(create_app()).post("/api/v1/georeferencing/fit", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["quality_status"] == "unverified"
    assert body["report"]["control_point_count"] == 5
    assert body["report"]["rmse_metres"] < 1e-6
    assert body["boundary"]["geometry"]["type"] == "Polygon"
    assert body["boundary"]["properties"]["quality_status"] == "unverified"


def test_fit_endpoint_rejects_collinear_points_with_stable_error() -> None:
    request = payload()
    request["control_points"] = request["control_points"][:3]
    for index, point in enumerate(request["control_points"]):
        point["pixel_x"] = index
        point["pixel_y"] = index

    response = TestClient(create_app()).post("/api/v1/georeferencing/fit", json=request)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "GEOREFERENCING_FIT_REJECTED"


def test_fit_endpoint_rejects_point_outside_image() -> None:
    request = payload()
    request["control_points"][0]["pixel_x"] = 9000

    response = TestClient(create_app()).post("/api/v1/georeferencing/fit", json=request)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CONTRACT_VALIDATION_FAILED"
