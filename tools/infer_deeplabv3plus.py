"""Run recorded DeepLabV3+ inference and create geospatial-style QA artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import segmentation_models_pytorch as smp
import torch
from PIL import Image, ImageDraw
from torch.utils.data import DataLoader
from tqdm import tqdm

from oge_main.data.dataset import FarmSegmentationDataset
from oge_main.metrics import BinarySegmentationMetrics, binary_sample_metrics
from oge_main.utils.device import select_device


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "validation", "test"), default="test")
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("outputs/inference/deeplabv3plus_epoch3_test"),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_revision() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() or None


def git_is_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=False
    )
    return bool(result.stdout.strip())


def stretch_rgb(image: np.ndarray, valid: np.ndarray) -> np.ndarray:
    output = np.zeros_like(image, dtype=np.uint8)
    for channel in range(3):
        values = image[channel]
        sample = values[valid]
        low, high = np.percentile(sample, (2, 98)) if sample.size else (0, 1)
        output[channel] = (
            np.clip((values - low) / max(high - low, 1e-6), 0, 1) * 255
        ).astype(np.uint8)
    return np.moveaxis(output, 0, -1)


def overlay(rgb: np.ndarray, mask: np.ndarray, color: tuple[int, int, int]) -> np.ndarray:
    result = rgb.copy()
    result[mask] = (0.50 * result[mask] + 0.50 * np.asarray(color)).astype(np.uint8)
    return result


def error_map(
    prediction: np.ndarray, target: np.ndarray, valid: np.ndarray
) -> np.ndarray:
    prediction = prediction.astype(bool)
    target = target.astype(bool)
    valid = valid.astype(bool)
    result = np.zeros((*target.shape, 3), dtype=np.uint8)
    result[valid] = (35, 39, 47)
    result[prediction & target & valid] = (34, 197, 94)
    result[prediction & ~target & valid] = (249, 115, 22)
    result[~prediction & target & valid] = (239, 68, 68)
    return result


def visualization_card(
    sample_id: str,
    image: np.ndarray,
    target: np.ndarray,
    prediction: np.ndarray,
    valid: np.ndarray,
    metrics: dict[str, Any],
    panel_size: int = 256,
) -> Image.Image:
    rgb = stretch_rgb(image, valid)
    panels = (
        ("input", rgb),
        ("label", overlay(rgb, target.astype(bool), (239, 68, 68))),
        ("prediction", overlay(rgb, prediction.astype(bool), (34, 197, 94))),
        ("error", error_map(prediction, target, valid)),
    )
    header = 46
    card = Image.new("RGB", (panel_size * 4, panel_size + header), "white")
    draw = ImageDraw.Draw(card)
    draw.text(
        (4, 4),
        f"{sample_id}  IoU={metrics['iou']:.3f}  P={metrics['precision']:.3f}  "
        f"R={metrics['recall']:.3f}",
        fill="black",
    )
    for index, (title, panel) in enumerate(panels):
        resampling = Image.Resampling.NEAREST if title == "error" else Image.Resampling.BILINEAR
        rendered = Image.fromarray(panel).resize(
            (panel_size, panel_size), resampling
        )
        card.paste(rendered, (index * panel_size, header))
        draw.text((index * panel_size + 4, 26), title, fill="black")
    return card


def write_prediction_tiffs(
    source_path: Path,
    probability: np.ndarray,
    prediction: np.ndarray,
    probability_path: Path,
    prediction_path: Path,
) -> None:
    with rasterio.open(source_path) as source:
        profile = source.profile.copy()
    profile.update(count=1, tiled=False, compress="lzw", nodata=None)
    probability_uint16 = np.round(np.clip(probability, 0, 1) * 65535).astype(np.uint16)
    probability_profile = {**profile, "dtype": "uint16"}
    prediction_profile = {**profile, "dtype": "uint8"}
    with rasterio.open(probability_path, "w", **probability_profile) as destination:
        destination.write(probability_uint16, 1)
    with rasterio.open(prediction_path, "w", **prediction_profile) as destination:
        destination.write(prediction.astype(np.uint8), 1)


def main() -> None:
    args = parse_arguments()
    if not 0 < args.threshold < 1:
        raise ValueError("threshold must be between 0 and 1")
    if args.output_directory.exists():
        if not args.overwrite:
            raise FileExistsError(
                f"{args.output_directory} already exists; use --overwrite or another directory"
            )
        shutil.rmtree(args.output_directory)
    args.output_directory.mkdir(parents=True)
    probability_directory = args.output_directory / "probabilities"
    prediction_directory = args.output_directory / "predictions"
    visualization_directory = args.output_directory / "visualizations"
    for directory in (probability_directory, prediction_directory, visualization_directory):
        directory.mkdir()

    started = time.time()
    device = select_device()
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    configuration = checkpoint["configuration"]
    model_configuration = configuration["model"]
    model = smp.DeepLabV3Plus(
        encoder_name=model_configuration["encoder"],
        encoder_weights=None,
        in_channels=3,
        classes=1,
    ).to(device)
    model.load_state_dict(checkpoint["model"])
    model.eval()

    data_configuration = configuration["data"]
    dataset = FarmSegmentationDataset(
        args.split,
        split_file=data_configuration["split_file"],
        statistics_file=data_configuration["statistics_file"],
        root=data_configuration.get("dataset_root"),
    )
    batch_size = args.batch_size or int(configuration["training"]["batch_size"])
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=args.num_workers,
    )
    global_metrics = BinarySegmentationMetrics(args.threshold)
    rows: list[dict[str, Any]] = []

    with torch.inference_mode():
        for batch in tqdm(loader, desc=f"infer {args.split}"):
            logits = model(batch["image"].to(device)).cpu()
            probabilities = torch.sigmoid(logits[:, 0]).numpy()
            predictions = probabilities >= args.threshold
            global_metrics.update(logits, batch["mask"], batch["valid_mask"])
            for batch_index, sample_id in enumerate(batch["sample_id"]):
                dataset_index = next(
                    index
                    for index, pair in enumerate(dataset.samples)
                    if pair.sample_id == sample_id
                )
                pair = dataset.samples[dataset_index]
                valid = batch["valid_mask"][batch_index].numpy()
                target = batch["mask"][batch_index].numpy().astype(np.uint8)
                prediction = predictions[batch_index] & valid
                probability = probabilities[batch_index]
                probability[~valid] = 0
                metrics = binary_sample_metrics(prediction, target, valid)
                row = {"sample_id": sample_id, **metrics}
                rows.append(row)
                write_prediction_tiffs(
                    pair.image,
                    probability,
                    prediction,
                    probability_directory / f"{sample_id}.tif",
                    prediction_directory / f"{sample_id}.tif",
                )

    rows.sort(key=lambda row: row["iou"])
    with (args.output_directory / "per_sample_metrics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    count = len(rows)
    selected_rows = rows[:3] + rows[count // 2 - 1 : count // 2 + 2] + rows[-3:]
    cards: list[Image.Image] = []
    pairs_by_id = {pair.sample_id: pair for pair in dataset.samples}
    for rank, row in enumerate(selected_rows):
        sample_id = row["sample_id"]
        pair = pairs_by_id[sample_id]
        with rasterio.open(pair.image) as source:
            image = source.read().astype(np.float32)
        with rasterio.open(pair.mask) as source:
            target = source.read(1)
        valid = np.any(image != 0, axis=0)
        with rasterio.open(probability_directory / f"{sample_id}.tif") as source:
            normalized_probability = source.read(1).astype(np.float32) / 65535
        prediction = normalized_probability >= args.threshold
        card = visualization_card(sample_id, image, target, prediction, valid, row)
        label = "worst" if rank < 3 else "median" if rank < 6 else "best"
        card.save(visualization_directory / f"{label}_{sample_id}.jpg", quality=92)
        cards.append(card.resize((768, 226), Image.Resampling.LANCZOS))

    sheet = Image.new("RGB", (768, 226 * len(cards)), "#d1d5db")
    for index, card in enumerate(cards):
        sheet.paste(card, (0, index * 226))
    sheet.save(args.output_directory / "representative_cases.jpg", quality=92)

    summary = {
        "created_at": datetime.now().astimezone().isoformat(),
        "git_revision": git_revision(),
        "git_dirty": git_is_dirty(),
        "checkpoint": str(args.checkpoint.resolve()),
        "checkpoint_sha256": file_sha256(args.checkpoint),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "model": {
            "architecture": "DeepLabV3Plus",
            "encoder": model_configuration["encoder"],
            "input_channels": 3,
            "classes": 1,
        },
        "split": args.split,
        "sample_count": len(dataset),
        "threshold": args.threshold,
        "threshold_source": "validation sweep from threshold_calibration.json",
        "device": str(device),
        "elapsed_seconds": round(time.time() - started, 2),
        "global_metrics": global_metrics.compute(),
        "sample_iou_distribution": {
            "minimum": float(rows[0]["iou"]),
            "p25": float(np.percentile([row["iou"] for row in rows], 25)),
            "median": float(np.median([row["iou"] for row in rows])),
            "p75": float(np.percentile([row["iou"] for row in rows], 75)),
            "maximum": float(rows[-1]["iou"]),
        },
        "artifacts": {
            "probabilities": "probabilities/*.tif (uint16 maps 0..65535 to 0..1)",
            "predictions": "predictions/*.tif (uint8 binary masks)",
            "per_sample_metrics": "per_sample_metrics.csv",
            "representative_cases": "representative_cases.jpg",
        },
    }
    (args.output_directory / "inference_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
