"""Run a recorded segmentation model on one large georeferenced RGB image.

The source may be an ordinary PNG/JPEG when an audited georeferencing fit is
provided. Overlapping tiles are blended in probability space before the binary
mask and validation metrics are produced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
import segmentation_models_pytorch as smp
import torch
from PIL import Image
from rasterio.transform import Affine

from oge_main.metrics import binary_sample_metrics
from oge_main.utils.device import select_device

MU_IN_SQUARE_METERS = 2000 / 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-image", type=Path, required=True)
    parser.add_argument("--fit-response", type=Path, required=True)
    parser.add_argument("--valid-mask", type=Path, required=True)
    parser.add_argument("--reference-mask", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument(
        "--target",
        choices=("cultivated_land_candidate", "rice_field_candidate"),
        default="cultivated_land_candidate",
    )
    parser.add_argument("--threshold", type=float, default=0.70)
    parser.add_argument("--tile-size", type=int, default=512)
    parser.add_argument("--overlap", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--maximum-windows", type=int)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_binary(path: Path) -> np.ndarray:
    array = np.asarray(Image.open(path).convert("L"))
    values = np.unique(array)
    if not np.isin(values, [0, 1, 255]).all():
        raise ValueError(f"binary mask contains unsupported values: {path}")
    return array > 0


def fit_transform(path: Path) -> tuple[Affine, str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = payload["report"]
    east = report["coefficients_easting"]
    north = report["coefficients_northing"]
    return (
        Affine(east[1], east[2], east[0], north[1], north[2], north[0]),
        report["projected_crs"],
        report,
    )


def positions(length: int, tile_size: int, stride: int) -> list[int]:
    if length <= tile_size:
        return [0]
    values = list(range(0, length - tile_size + 1, stride))
    if values[-1] != length - tile_size:
        values.append(length - tile_size)
    return values


def blending_weights(tile_size: int) -> np.ndarray:
    axis = np.hanning(tile_size).astype(np.float32)
    weights = np.outer(axis, axis)
    # Keep image edges numerically stable when a border is covered by one tile.
    return np.maximum(weights, 0.05).astype(np.float32)


def load_model(path: Path, device: torch.device) -> tuple[torch.nn.Module, dict]:
    checkpoint = torch.load(path, map_location=device, weights_only=False)
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


def write_raster(
    path: Path,
    array: np.ndarray,
    *,
    transform: Affine,
    crs: str,
    dtype: str,
    nodata: int = 0,
) -> None:
    count = 1 if array.ndim == 2 else array.shape[2]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=count,
        dtype=dtype,
        crs=crs,
        transform=transform,
        nodata=nodata,
        compress="deflate",
        tiled=True,
        blockxsize=512,
        blockysize=512,
    ) as destination:
        if array.ndim == 2:
            destination.write(array.astype(dtype), 1)
        else:
            destination.write(np.moveaxis(array.astype(dtype), -1, 0))


def preview(rgb: np.ndarray, prediction: np.ndarray, path: Path) -> None:
    scale = min(1.0, 1800 / max(rgb.shape[:2]))
    size = (max(1, round(rgb.shape[1] * scale)), max(1, round(rgb.shape[0] * scale)))
    image = Image.fromarray(rgb).resize(size, Image.Resampling.LANCZOS)
    mask = Image.fromarray((prediction * 255).astype(np.uint8)).resize(
        size, Image.Resampling.NEAREST
    )
    base = np.asarray(image).copy()
    selected = np.asarray(mask) > 0
    base[selected] = (
        0.45 * base[selected] + 0.55 * np.asarray([35, 201, 118])
    ).astype(np.uint8)
    Image.fromarray(base).save(path)


def validation_preview(
    rgb: np.ndarray,
    prediction: np.ndarray,
    reference: np.ndarray,
    valid: np.ndarray,
    path: Path,
) -> None:
    scale = min(1.0, 1800 / max(rgb.shape[:2]))
    size = (max(1, round(rgb.shape[1] * scale)), max(1, round(rgb.shape[0] * scale)))
    image = np.asarray(Image.fromarray(rgb).resize(size, Image.Resampling.LANCZOS)).copy()
    predicted = np.asarray(
        Image.fromarray((prediction * 255).astype(np.uint8)).resize(size, Image.Resampling.NEAREST)
    ) > 0
    target = np.asarray(
        Image.fromarray((reference * 255).astype(np.uint8)).resize(size, Image.Resampling.NEAREST)
    ) > 0
    usable = np.asarray(
        Image.fromarray((valid * 255).astype(np.uint8)).resize(size, Image.Resampling.NEAREST)
    ) > 0
    colors = np.zeros_like(image)
    colors[predicted & target & usable] = (31, 190, 96)  # true positive
    colors[predicted & ~target & usable] = (245, 145, 32)  # false positive
    colors[~predicted & target & usable] = (226, 65, 65)  # false negative
    selected = np.any(colors > 0, axis=2)
    image[selected] = (0.35 * image[selected] + 0.65 * colors[selected]).astype(np.uint8)
    Image.fromarray(image).save(path)


def main() -> None:
    args = parse_args()
    if not 0 < args.threshold < 1:
        raise ValueError("threshold must be between zero and one")
    if args.overlap < 0 or args.overlap >= args.tile_size:
        raise ValueError("overlap must be non-negative and smaller than tile size")

    Image.MAX_IMAGE_PIXELS = None
    rgb = np.asarray(Image.open(args.source_image).convert("RGB"))
    valid = read_binary(args.valid_mask)
    if valid.shape != rgb.shape[:2]:
        raise ValueError("valid mask and RGB image dimensions differ")
    reference = read_binary(args.reference_mask) if args.reference_mask else None
    if reference is not None and reference.shape != valid.shape:
        raise ValueError("reference mask and RGB image dimensions differ")

    transform, crs, fit_report = fit_transform(args.fit_response)
    device = select_device()
    model, checkpoint = load_model(args.checkpoint, device)

    source_mean = rgb[valid].mean(axis=0).astype(np.float32)
    source_std = np.maximum(rgb[valid].std(axis=0), 1.0).astype(np.float32)
    stride = args.tile_size - args.overlap
    all_windows = [
        (row, col)
        for row in positions(rgb.shape[0], args.tile_size, stride)
        for col in positions(rgb.shape[1], args.tile_size, stride)
    ]
    eligible_windows = [
        (row, col)
        for row, col in all_windows
        if valid[row : row + args.tile_size, col : col + args.tile_size].any()
    ]
    windows = eligible_windows
    if args.maximum_windows is not None:
        windows = windows[: args.maximum_windows]

    args.output_directory.mkdir(parents=True, exist_ok=True)
    weights = blending_weights(args.tile_size)
    with tempfile.TemporaryDirectory(prefix="oge-large-inference-") as temporary:
        probability_sum = np.memmap(
            Path(temporary) / "probability.dat",
            mode="w+",
            dtype=np.float32,
            shape=valid.shape,
        )
        weight_sum = np.memmap(
            Path(temporary) / "weights.dat",
            mode="w+",
            dtype=np.float32,
            shape=valid.shape,
        )
        probability_sum[:] = 0
        weight_sum[:] = 0

        for offset in range(0, len(windows), args.batch_size):
            batch_windows = windows[offset : offset + args.batch_size]
            tensors = []
            valid_tiles = []
            for row, col in batch_windows:
                tile = rgb[row : row + args.tile_size, col : col + args.tile_size]
                tile_valid = valid[row : row + args.tile_size, col : col + args.tile_size]
                normalized = (tile.astype(np.float32) - source_mean) / source_std
                normalized[~tile_valid] = 0
                tensors.append(np.moveaxis(normalized, -1, 0))
                valid_tiles.append(tile_valid)
            tensor = torch.from_numpy(np.stack(tensors)).float().to(device)
            with torch.inference_mode():
                probabilities = torch.sigmoid(model(tensor))[:, 0].cpu().numpy()
            for (row, col), probability, tile_valid in zip(
                batch_windows, probabilities, valid_tiles, strict=True
            ):
                active_weights = weights * tile_valid
                target = np.s_[row : row + args.tile_size, col : col + args.tile_size]
                probability_sum[target] += probability * active_weights
                weight_sum[target] += active_weights
            print(f"processed {min(offset + args.batch_size, len(windows))}/{len(windows)} tiles", flush=True)

        covered = weight_sum > 0
        probability = np.zeros(valid.shape, dtype=np.float32)
        probability[covered] = probability_sum[covered] / weight_sum[covered]
        prediction = (probability >= args.threshold) & valid & covered

    probability_path = args.output_directory / "candidate-probability.tif"
    mask_path = args.output_directory / "candidate-mask.tif"
    source_path = args.output_directory / "source-rgb.tif"
    write_raster(source_path, rgb, transform=transform, crs=crs, dtype="uint8", nodata=255)
    write_raster(
        probability_path,
        np.round(probability * 65535),
        transform=transform,
        crs=crs,
        dtype="uint16",
    )
    write_raster(mask_path, prediction.astype(np.uint8), transform=transform, crs=crs, dtype="uint8")
    preview(rgb, prediction, args.output_directory / "candidate-overlay.png")

    pixel_area_m2 = abs(transform.a * transform.e - transform.b * transform.d)
    metrics = None
    if reference is not None:
        evaluation_valid = valid & covered
        metrics = binary_sample_metrics(prediction, reference, evaluation_valid)
        metrics.update(
            {
                "reference_area_m2": round(float(reference[evaluation_valid].sum() * pixel_area_m2), 2),
                "prediction_area_m2": round(float(prediction[evaluation_valid].sum() * pixel_area_m2), 2),
            }
        )
        metrics["reference_area_mu"] = round(metrics["reference_area_m2"] / MU_IN_SQUARE_METERS, 2)
        metrics["prediction_area_mu"] = round(metrics["prediction_area_m2"] / MU_IN_SQUARE_METERS, 2)
        metrics["area_difference_mu"] = round(metrics["prediction_area_mu"] - metrics["reference_area_mu"], 2)
        validation_preview(
            rgb,
            prediction,
            reference,
            evaluation_valid,
            args.output_directory / "validation-overlay.png",
        )

    metadata = {
        "run_id": f"model-run.{args.scene_id}.{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "review_required",
        "model": {
            "architecture": "DeepLabV3Plus",
            "encoder": checkpoint["configuration"]["model"]["encoder"],
            "checkpoint": str(args.checkpoint.resolve()),
            "checkpoint_sha256": sha256(args.checkpoint),
            "checkpoint_epoch": int(checkpoint["epoch"]),
            "threshold": args.threshold,
            "target": args.target,
        },
        "input": {
            "source_image": str(args.source_image.resolve()),
            "source_sha256": sha256(args.source_image),
            "width": rgb.shape[1],
            "height": rgb.shape[0],
            "crs": crs,
            "fit_rmse_metres": fit_report["rmse_metres"],
            "normalization": "valid-pixel scene standardization",
            "source_mean_rgb": source_mean.tolist(),
            "source_std_rgb": source_std.tolist(),
        },
        "execution": {
            "device": str(device),
            "tile_size": args.tile_size,
            "overlap": args.overlap,
            "window_count": len(windows),
            "eligible_window_count": len(eligible_windows),
            "skipped_empty_window_count": len(all_windows) - len(eligible_windows),
            "partial_run": args.maximum_windows is not None,
            "covered_fraction": round(float(covered.mean()), 6),
        },
        "outputs": {
            "source_rgb": str(source_path),
            "probability": str(probability_path),
            "mask": str(mask_path),
            "overlay": str(args.output_directory / "candidate-overlay.png"),
            "validation_overlay": (
                str(args.output_directory / "validation-overlay.png")
                if reference is not None
                else None
            ),
        },
        "validation": metrics,
        "warning": "Model candidate result; requires review before business area use.",
    }
    (args.output_directory / "model-run.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
