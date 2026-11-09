"""Streaming binary segmentation metrics with invalid-pixel masking."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch


@dataclass
class BinarySegmentationMetrics:
    threshold: float = 0.5
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0
    true_negative: int = 0

    def update(
        self, logits: torch.Tensor, targets: torch.Tensor, valid_mask: torch.Tensor
    ) -> None:
        if logits.ndim == 4 and logits.shape[1] == 1:
            logits = logits[:, 0]
        valid = valid_mask.bool()
        predictions = torch.sigmoid(logits) >= self.threshold
        targets_bool = targets.bool()
        self.true_positive += int(torch.sum(predictions & targets_bool & valid).item())
        self.false_positive += int(torch.sum(predictions & ~targets_bool & valid).item())
        self.false_negative += int(torch.sum(~predictions & targets_bool & valid).item())
        self.true_negative += int(torch.sum(~predictions & ~targets_bool & valid).item())

    def compute(self) -> dict[str, float]:
        epsilon = 1e-8
        tp = self.true_positive
        fp = self.false_positive
        fn = self.false_negative
        tn = self.true_negative
        return {
            "iou": tp / (tp + fp + fn + epsilon),
            "f1": 2 * tp / (2 * tp + fp + fn + epsilon),
            "precision": tp / (tp + fp + epsilon),
            "recall": tp / (tp + fn + epsilon),
            "accuracy": (tp + tn) / (tp + tn + fp + fn + epsilon),
        }


def binary_sample_metrics(
    prediction: np.ndarray, target: np.ndarray, valid: np.ndarray
) -> dict[str, float | int]:
    """Compute per-sample metrics while excluding invalid source-image pixels."""
    prediction = prediction.astype(bool)
    target = target.astype(bool)
    valid = valid.astype(bool)
    true_positive = int(np.sum(prediction & target & valid))
    false_positive = int(np.sum(prediction & ~target & valid))
    false_negative = int(np.sum(~prediction & target & valid))
    true_negative = int(np.sum(~prediction & ~target & valid))
    epsilon = 1e-8
    return {
        "iou": true_positive / (true_positive + false_positive + false_negative + epsilon),
        "f1": 2 * true_positive
        / (2 * true_positive + false_positive + false_negative + epsilon),
        "precision": true_positive / (true_positive + false_positive + epsilon),
        "recall": true_positive / (true_positive + false_negative + epsilon),
        "accuracy": (true_positive + true_negative)
        / (true_positive + true_negative + false_positive + false_negative + epsilon),
        "valid_fraction": float(valid.mean()),
        "target_fraction": float(target[valid].mean()),
        "prediction_fraction": float(prediction[valid].mean()),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
    }

