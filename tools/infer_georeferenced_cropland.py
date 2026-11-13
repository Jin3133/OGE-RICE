"""Run the current cropland baseline on georeferenced multispectral imagery."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import rasterio
import segmentation_models_pytorch as smp
import torch
from PIL import Image

from oge_main.utils.device import select_device

MU_IN_SQUARE_METERS = 666.6666666667


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--grid-id", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--statistics", type=Path, default=Path("data/statistics/oge_farm_v2.json"))
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument(
        "--normalization-mode",
        choices=("training_statistics", "scene_standardized"),
        default="training_statistics",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def stretch_rgb(data: np.ndarray, valid: np.ndarray) -> np.ndarray:
    rgb = data.astype(np.float32)
    output = np.zeros_like(rgb, dtype=np.uint8)
    for index in range(3):
        values = rgb[index][valid]
        low, high = np.percentile(values, [2, 98]) if values.size else (0, 1)
        output[index] = (
            np.clip((rgb[index] - low) / max(high - low, 1), 0, 1) * 255
        ).astype(np.uint8)
    return np.moveaxis(output, 0, -1)


def write_single_band(path: Path, array: np.ndarray, profile: dict, dtype: str) -> None:
    output_profile = profile.copy()
    output_profile.update(
        count=1,
        dtype=dtype,
        nodata=0,
        compress="deflate",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    with rasterio.open(path, "w", **output_profile) as destination:
        destination.write(array.astype(dtype), 1)


def load_model(checkpoint_path: Path, device: torch.device) -> tuple[torch.nn.Module, dict]:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    configuration = checkpoint["configuration"]
    model = smp.DeepLabV3Plus(
        encoder_name=configuration["model"]["encoder"],
        encoder_weights=None,
        in_channels=3,
        classes=1,
    ).to(device)
    model.load_state_dict(checkpoint["model"])
    model.eval()
    return model, checkpoint


def main() -> None:
    args = parse_args()
    if not 0 < args.threshold < 1:
        raise ValueError("threshold must be between 0 and 1")
    statistics = json.loads(args.statistics.read_text(encoding="utf-8"))
    mean = np.asarray(statistics["mean"], dtype=np.float32)[:, None, None]
    std = np.asarray(statistics["std"], dtype=np.float32)[:, None, None]
    device = select_device()
    model, checkpoint = load_model(args.checkpoint, device)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    inputs = sorted((args.input_dir / args.grid_id).glob("*_MS4.tif"))
    if not inputs:
        raise RuntimeError(f"No MS4 GeoTIFFs found for {args.grid_id}")
    rows = []
    for input_path in inputs:
        date_token = input_path.stem.split("_")[-2]
        clear_path = input_path.with_name(
            input_path.name.replace("_MS4.tif", "_CLEAR10m.tif")
        )
        with rasterio.open(input_path) as source:
            data4 = source.read().astype(np.float32)
            profile = source.profile.copy()
            transform = source.transform
            tags = source.tags()
        # The OGE track-three training previews are natural-color RGB, while the
        # demo GeoTIFF stores B02, B03, B04, B08. Reorder to B04, B03, B02.
        data = data4[[2, 1, 0]]
        valid = np.all(data > 0, axis=0)
        if clear_path.exists():
            with rasterio.open(clear_path) as source:
                valid &= source.read(1).astype(bool)
        if args.normalization_mode == "scene_standardized":
            scene_mean = np.asarray(
                [channel[valid].mean() for channel in data], dtype=np.float32
            )[:, None, None]
            scene_std = np.asarray(
                [channel[valid].std() for channel in data], dtype=np.float32
            )[:, None, None]
            normalized = (data - scene_mean) / np.maximum(scene_std, 1e-6)
        else:
            normalized = (data - mean) / std
        normalized[:, ~valid] = 0
        original_height, original_width = normalized.shape[1:]
        padded_height = ((original_height + 15) // 16) * 16
        padded_width = ((original_width + 15) // 16) * 16
        padded = np.zeros((3, padded_height, padded_width), dtype=np.float32)
        padded[:, :original_height, :original_width] = normalized
        tensor = torch.from_numpy(padded[None]).float().to(device)
        with torch.inference_mode():
            probability = torch.sigmoid(model(tensor))[0, 0].cpu().numpy()
        probability = probability[:original_height, :original_width]
        probability[~valid] = 0
        prediction = (probability >= args.threshold) & valid

        prefix = f"{args.grid_id}_{date_token}_cultivated_candidate"
        probability_path = args.output_dir / f"{prefix}_probability.tif"
        mask_path = args.output_dir / f"{prefix}_mask.tif"
        write_single_band(
            probability_path,
            np.round(probability * 65535),
            profile,
            "uint16",
        )
        write_single_band(mask_path, prediction.astype(np.uint8), profile, "uint8")

        rgb = stretch_rgb(data, valid)
        overlay = rgb.copy()
        overlay[prediction] = (
            0.45 * overlay[prediction] + 0.55 * np.array([38, 208, 124])
        ).astype(np.uint8)
        Image.fromarray(overlay).save(args.output_dir / f"{prefix}_overlay.png")

        pixel_area_m2 = abs(transform.a * transform.e)
        area_m2 = float(prediction.sum() * pixel_area_m2)
        rows.append(
            {
                "grid_id": args.grid_id,
                "date": tags.get("acquisition_date", date_token),
                "scene_id": tags.get("scene_id", ""),
                "model_target": "cultivated_land",
                "threshold": args.threshold,
                "valid_fraction": round(float(valid.mean()), 6),
                "candidate_fraction_of_valid": round(
                    float(prediction.sum() / max(valid.sum(), 1)), 6
                ),
                "candidate_area_m2": round(area_m2, 2),
                "candidate_area_mu": round(area_m2 / MU_IN_SQUARE_METERS, 2),
                "probability_mean_valid": round(float(probability[valid].mean()), 6),
                "mask_path": str(mask_path),
                "probability_path": str(probability_path),
            }
        )
        print(
            f"{date_token}: fraction={rows[-1]['candidate_fraction_of_valid']:.3f}, "
            f"area={rows[-1]['candidate_area_mu']:.1f} mu",
            flush=True,
        )

    summary_path = args.output_dir / f"{args.grid_id}_transfer_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    run_metadata = {
        "checkpoint": str(args.checkpoint),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "threshold": args.threshold,
        "input_channels": ["B04", "B03", "B02"],
        "normalization_source": str(args.statistics),
        "normalization_mode": args.normalization_mode,
        "output_semantics": "cultivated_land_candidate",
        "warning": "Cross-sensor transfer test; results require visual review before area use.",
    }
    (args.output_dir / "run_metadata.json").write_text(
        json.dumps(run_metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(summary_path)


if __name__ == "__main__":
    main()
