from __future__ import annotations

import cv2
import numpy as np
import pytest

from oge_main.application import suggest_control_points


def encoded_test_pair() -> tuple[bytes, bytes]:
    rng = np.random.default_rng(20261119)
    source = np.full((700, 900, 3), 238, dtype=np.uint8)
    for _ in range(160):
        x, y = rng.integers([25, 25], [875, 675])
        colour = tuple(int(value) for value in rng.integers(20, 220, size=3))
        cv2.circle(source, (int(x), int(y)), int(rng.integers(3, 13)), colour, -1)
    cv2.putText(source, "IRRIGATION 51", (110, 350), cv2.FONT_HERSHEY_SIMPLEX, 2, (5, 5, 5), 5)
    matrix = np.float32([[0.93, -0.08, 75], [0.07, 0.93, 42]])
    reference = cv2.warpAffine(source, matrix, (980, 780), borderValue=(245, 245, 245))
    return cv2.imencode(".png", source)[1].tobytes(), cv2.imencode(".png", reference)[1].tobytes()


def test_suggests_spatially_distributed_ransac_inliers() -> None:
    source, reference = encoded_test_pair()
    result = suggest_control_points(source, reference, maximum_points=10)

    assert result.method == "sift_affine_ransac_v1"
    assert result.detected_matches >= result.ransac_inliers >= 4
    assert 4 <= len(result.points) <= 10
    assert len({(int(point.pixel_x // 225), int(point.pixel_y // 175)) for point in result.points}) >= 3
    assert len({(round(point.pixel_x), round(point.pixel_y)) for point in result.points}) == len(result.points)
    assert len({(round(point.reference_x), round(point.reference_y)) for point in result.points}) == len(result.points)


def test_rejects_featureless_images() -> None:
    image = cv2.imencode(".png", np.zeros((300, 300, 3), dtype=np.uint8))[1].tobytes()
    with pytest.raises(ValueError, match="not enough visual features"):
        suggest_control_points(image, image)
