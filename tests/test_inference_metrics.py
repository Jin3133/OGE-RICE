import numpy as np
import pytest

from oge_main.metrics import binary_sample_metrics


def test_sample_metrics_ignore_invalid_pixels() -> None:
    prediction = np.array([[1, 0], [1, 1]], dtype=np.uint8)
    target = np.array([[1, 0], [0, 0]], dtype=np.uint8)
    valid = np.array([[1, 1], [1, 0]], dtype=bool)
    metrics = binary_sample_metrics(prediction, target, valid)
    assert metrics["iou"] == pytest.approx(0.5)
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == pytest.approx(1.0)
