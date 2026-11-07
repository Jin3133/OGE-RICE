"""Create compact image/mask/overlay sheets for manual dataset QA."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw

from oge_main.data.inventory import paired_samples
from oge_main.data.paths import dataset_root


def stretch_rgb(image: np.ndarray) -> np.ndarray:
    rgb = np.moveaxis(image, 0, -1).astype(np.float32)
    valid = np.any(rgb > 0, axis=2)
    output = np.zeros_like(rgb, dtype=np.uint8)
    for channel in range(3):
        values = rgb[:, :, channel]
        sample = values[valid]
        low, high = np.percentile(sample, (2, 98)) if sample.size else (0, 1)
        output[:, :, channel] = (
            np.clip((values - low) / max(high - low, 1), 0, 1) * 255
        ).astype(np.uint8)
    return output


def tile_for(sample_id: str, image_path: Path, mask_path: Path, size: int = 192) -> Image.Image:
    with rasterio.open(image_path) as source:
        image = source.read()
    with rasterio.open(mask_path) as source:
        mask = source.read(1).astype(bool)
    rgb = stretch_rgb(image)
    overlay = rgb.copy()
    overlay[mask] = (0.55 * overlay[mask] + 0.45 * np.array([255, 32, 32])).astype(np.uint8)
    rgb_image = Image.fromarray(rgb).resize((size, size), Image.Resampling.BILINEAR)
    overlay_image = Image.fromarray(overlay).resize((size, size), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (size * 2, size + 24), "white")
    canvas.paste(rgb_image, (0, 24))
    canvas.paste(overlay_image, (size, 24))
    ImageDraw.Draw(canvas).text((4, 4), sample_id, fill="black")
    return canvas


def main() -> None:
    with Path("outputs/audit/sample_quality.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    selections = {
        "high_zero": sorted(
            rows, key=lambda row: float(row["band1_zero_fraction"]), reverse=True
        )[:12],
        "low_contrast": sorted(rows, key=lambda row: float(row["band1_std"]))[:12],
        "foreground_extremes": sorted(rows, key=lambda row: float(row["foreground_fraction"]))[:6]
        + sorted(rows, key=lambda row: float(row["foreground_fraction"]), reverse=True)[:6],
        "near_duplicates": sorted(
            rows, key=lambda row: float(row["nearest_similarity"]), reverse=True
        )[:12],
    }
    pairs = {pair.sample_id: pair for pair in paired_samples(dataset_root())}
    output = Path("outputs/audit/contact_sheets")
    output.mkdir(parents=True, exist_ok=True)
    for name, selected in selections.items():
        tiles = [tile_for(row["sample_id"], pairs[row["sample_id"]].image, pairs[row["sample_id"]].mask) for row in selected]
        sheet = Image.new("RGB", (384 * 3, 216 * 4), "#dddddd")
        for index, tile in enumerate(tiles):
            sheet.paste(tile, ((index % 3) * 384, (index // 3) * 216))
        sheet.save(output / f"{name}.jpg", quality=92)
        print(output / f"{name}.jpg")


if __name__ == "__main__":
    main()
