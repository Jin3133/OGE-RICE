"""Evaluate a weak-reference cropland model over a spatial holdout split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import segmentation_models_pytorch as smp
import torch
from torch.utils.data import DataLoader

from oge_main.data.weak_cropland_dataset import WeakCroplandDataset
from oge_main.utils.device import select_device


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "validation", "test"), default="test")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/splits/sentinel_cropland_weak_v1.json"),
    )
    parser.add_argument(
        "--statistics",
        type=Path,
        default=Path("data/statistics/sentinel_cropland_weak_v1.json"),
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    device = select_device()
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    model_config = checkpoint["configuration"]["model"]
    model = smp.DeepLabV3Plus(
        encoder_name=model_config["encoder"],
        encoder_weights=None,
        in_channels=3,
        classes=1,
    ).to(device)
    model.load_state_dict(checkpoint["model"])
    model.eval()
    dataset = WeakCroplandDataset(args.split, args.manifest, args.statistics)
    loader = DataLoader(dataset, batch_size=1, shuffle=False)

    probabilities: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    sample_rows = []
    with torch.inference_mode():
        for batch in loader:
            probability = torch.sigmoid(model(batch["image"].to(device)))[0, 0].cpu().numpy()
            target = batch["mask"][0].numpy().astype(bool)
            valid = batch["valid_mask"][0].numpy().astype(bool)
            probabilities.append(probability[valid])
            targets.append(target[valid])
            sample_rows.append(
                {
                    "sample_id": batch["sample_id"][0],
                    "mean_probability": float(probability[valid].mean()),
                    "predicted_fraction_at_0_5": float((probability[valid] >= 0.5).mean()),
                    "weak_reference_fraction": float(target[valid].mean()),
                }
            )
    probability = np.concatenate(probabilities)
    target = np.concatenate(targets)
    threshold_rows = []
    for threshold in np.arange(0.1, 0.91, 0.05):
        prediction = probability >= threshold
        tp = int(np.logical_and(prediction, target).sum())
        fp = int(np.logical_and(prediction, ~target).sum())
        fn = int(np.logical_and(~prediction, target).sum())
        iou = tp / max(tp + fp + fn, 1)
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        threshold_rows.append(
            {
                "threshold": round(float(threshold), 2),
                "iou": iou,
                "precision": precision,
                "recall": recall,
            }
        )
    result = {
        "checkpoint": str(args.checkpoint),
        "split": args.split,
        "best_by_iou": max(threshold_rows, key=lambda row: row["iou"]),
        "thresholds": threshold_rows,
        "samples": sample_rows,
        "caveat": "Metrics measure agreement with a 2023 annual-crops weak reference, not 2025 ground truth.",
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
