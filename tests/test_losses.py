import torch

from oge_main.losses import masked_bce_dice_loss


def test_invalid_pixels_do_not_change_loss() -> None:
    targets = torch.tensor([[[1.0, 0.0], [0.0, 1.0]]])
    valid = torch.tensor([[[True, True], [True, False]]])
    logits_a = torch.zeros((1, 1, 2, 2))
    logits_b = logits_a.clone()
    logits_b[0, 0, 1, 1] = 100.0
    assert torch.allclose(
        masked_bce_dice_loss(logits_a, targets, valid),
        masked_bce_dice_loss(logits_b, targets, valid),
    )

