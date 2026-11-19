from __future__ import annotations

import cv2
import numpy as np
from fastapi.testclient import TestClient
from rasterio.warp import transform

from oge_main.api import create_app
from oge_main.api.routes import georeferencing


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


def test_suggestion_endpoint_returns_review_candidates(monkeypatch) -> None:
    rng = np.random.default_rng(51)
    source = np.full((600, 800, 3), 235, dtype=np.uint8)
    for _ in range(140):
        x, y = rng.integers([20, 20], [780, 580])
        cv2.circle(source, (int(x), int(y)), 6, (20, 80, 140), -1)
    cv2.putText(source, "YUELAI", (160, 320), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 5)
    matrix = np.float32([[0.95, -0.05, 55], [0.04, 0.95, 38]])
    reference = cv2.warpAffine(source, matrix, (900, 700), borderValue=(245, 245, 245))
    source_bytes = cv2.imencode(".png", source)[1].tobytes()
    reference_bytes = cv2.imencode(".png", reference)[1].tobytes()

    class ReferenceResponse:
        content = reference_bytes

        @staticmethod
        def raise_for_status() -> None:
            return None

    monkeypatch.setattr(georeferencing.requests, "get", lambda *args, **kwargs: ReferenceResponse())
    response = TestClient(create_app()).post(
        "/api/v1/georeferencing/suggest",
        files={"source_image": ("source.png", source_bytes, "image/png")},
        data={
            "west": "121.3",
            "south": "31.8",
            "east": "121.6",
            "north": "32.0",
            "maximum_points": "8",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "review_required"
    assert body["method"] == "sift_affine_ransac_v1"
    assert 4 <= len(body["points"]) <= 8
    assert all(121.3 <= point["longitude"] <= 121.6 for point in body["points"])
    assert all(31.8 <= point["latitude"] <= 32.0 for point in body["points"])
