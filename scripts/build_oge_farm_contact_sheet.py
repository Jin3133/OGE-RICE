#!/usr/bin/env python3
"""Build a visual QC sheet for the OGE Wuhan-1 cropland dataset."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATASET = (
    ROOT
    / "data/raw/oge_wuhan1_farm/extracted"
    / "89d279976ef74625a1ea00d6cad512c1_farm/train"
)
AUDIT = ROOT / "data/catalog/oge_wuhan1_farm_audit.csv"
OUTPUT = ROOT / "data/raw/oge_wuhan1_farm/qc/oge_wuhan1_farm_contact_sheet.jpg"


def stretch(image: np.ndarray) -> np.ndarray:
    rgb = np.moveaxis(image.astype(np.float32), 0, -1)
    out = []
    for band in range(3):
        values = rgb[..., band]
        low, high = np.percentile(values, [2, 98])
        scaled = np.clip((values - low) / max(high - low, 1) * 255, 0, 255)
        out.append(scaled.astype(np.uint8))
    return np.stack(out, axis=-1)


def main() -> None:
    with AUDIT.open(encoding="utf-8-sig") as fh:
        rows = sorted(csv.DictReader(fh), key=lambda row: float(row["farm_fraction"]))
    positions = np.linspace(0, len(rows) - 1, 12).round().astype(int)
    selected = [rows[i] for i in positions]

    tile_size = 256
    caption = 34
    sheet = Image.new("RGB", (tile_size * 4, (tile_size + caption) * 3), "white")
    font = ImageFont.load_default()

    for index, row in enumerate(selected):
        sample = row["sample_id"]
        with rasterio.open(DATASET / "images" / f"{sample}.tif") as src:
            image = stretch(src.read())
        with rasterio.open(DATASET / "masks" / f"{sample}.tif") as src:
            mask = src.read(1).astype(bool)

        overlay = image.copy()
        overlay[mask] = (0.55 * overlay[mask] + 0.45 * np.array([255, 35, 35])).astype(np.uint8)
        tile = Image.fromarray(overlay).resize((tile_size, tile_size), Image.Resampling.LANCZOS)
        col, row_index = index % 4, index // 4
        x, y = col * tile_size, row_index * (tile_size + caption)
        sheet.paste(tile, (x, y))
        draw = ImageDraw.Draw(sheet)
        text = f"{sample}  farm={float(row['farm_fraction']):.1%}"
        draw.text((x + 6, y + tile_size + 8), text, fill="black", font=font)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUTPUT, quality=92)
    print(OUTPUT)


if __name__ == "__main__":
    main()
