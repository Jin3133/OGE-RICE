"""Streaming binary segmentation metrics with invalid-pixel masking."""

from __future__ import annotations

from dataclasses import dataclass

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

