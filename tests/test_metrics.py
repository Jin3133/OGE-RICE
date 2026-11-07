import pytest
import torch

from oge_main.metrics import BinarySegmentationMetrics


def test_metrics_ignore_invalid_pixels() -> None:
    logits = torch.tensor([[[[10.0, -10.0], [-10.0, 10.0]]]])
    targets = torch.tensor([[[1.0, 0.0], [1.0, 0.0]]])
    valid = torch.tensor([[[True, True], [True, False]]])
    metrics = BinarySegmentationMetrics()
    metrics.update(logits, targets, valid)
    result = metrics.compute()
    assert result["precision"] == pytest.approx(1.0)
    assert result["recall"] == pytest.approx(0.5)
