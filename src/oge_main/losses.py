"""Segmentation losses that exclude invalid source-image pixels."""

from __future__ import annotations

import torch
from torch.nn import functional


def masked_bce_dice_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    valid_mask: torch.Tensor,
    bce_weight: float = 0.5,
    smooth: float = 1.0,
) -> torch.Tensor:
    """Combine BCE and Dice while ignoring pixels outside the valid image footprint."""
    if logits.ndim == 4 and logits.shape[1] == 1:
        logits = logits[:, 0]
    targets = targets.float()
    valid = valid_mask.bool()
    if not torch.any(valid):
        return logits.sum() * 0.0

    bce = functional.binary_cross_entropy_with_logits(logits[valid], targets[valid])
    probabilities = torch.sigmoid(logits)[valid]
    selected_targets = targets[valid]
    intersection = torch.sum(probabilities * selected_targets)
    dice_loss = 1.0 - (2.0 * intersection + smooth) / (
        probabilities.sum() + selected_targets.sum() + smooth
    )
    return bce_weight * bce + (1.0 - bce_weight) * dice_loss

