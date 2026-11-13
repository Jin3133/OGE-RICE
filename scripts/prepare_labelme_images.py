#!/usr/bin/env python3
"""Create Labelme-ready previews from the Jiangxia GeoTIFF exports."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/raw/labeling/source_geotiff"
OUTPUT = ROOT / "data/raw/labeling/tolabel"
SOURCES = {
    "20250418": ("tci", "S2B_50RKU_20250418_0_L2A"),
    "20250614": ("tci", "S2A_50RKU_20250614_0_L2A"),
    "20250707": ("tci", "S2B_50RKU_20250707_0_L2A"),
    "20250816": ("ms4", "T50RKU_20250816T025529"),
    "20251005": ("ms4", "T50RKU_20251005T025529"),
}
GRIDS = ("JX5K_R03C06", "JX5K_R07C05", "JX5K_R10C10")


def stretch_rgb(image: np.ndarray) -> np.ndarray:
    """Apply an independent 2–98% linear stretch to each channel."""
    result = np.zeros(image.shape, dtype=np.uint8)
    valid = np.any(image > 0, axis=2)
    for channel in range(3):
        values = image[..., channel][valid]
        if values.size == 0:
            continue
        low, high = np.percentile(values, (2, 98))
        if high <= low:
            high = low + 1
        scaled = (image[..., channel].astype(np.float32) - low) * 255.0 / (high - low)
        result[..., channel] = np.clip(scaled, 0, 255).astype(np.uint8)
    result[~valid] = 0
    return result


def colorize_ndvi(ndvi: np.ndarray) -> np.ndarray:
    """Create a simple blue-yellow-green NDVI reference preview."""
    values = ndvi.astype(np.float32)
    valid = values > 0
    if not np.any(valid):
        return np.zeros((*ndvi.shape, 3), dtype=np.uint8)
    low, high = np.percentile(values[valid], (2, 98))
    if high <= low:
        high = low + 1
    norm = np.clip((values - low) / (high - low), 0, 1)
    rgb = np.zeros((*ndvi.shape, 3), dtype=np.uint8)
    rgb[..., 0] = np.where(norm < 0.5, 30 + norm * 400, 230 - (norm - 0.5) * 420)
    rgb[..., 1] = np.where(norm < 0.5, 80 + norm * 300, 230)
    rgb[..., 2] = np.where(norm < 0.5, 220 - norm * 320, 40)
    rgb[~valid] = 0
    return rgb


def main() -> None:
    image_dir = OUTPUT / "images_rgb"
    false_dir = OUTPUT / "reference_false_color"
    ndvi_dir = OUTPUT / "reference_ndvi"
    json_dir = OUTPUT / "annotations_json"
    for directory in (image_dir, false_dir, ndvi_dir, json_dir):
        directory.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    skipped: list[str] = []
    for grid in GRIDS:
        for date, (source_type, scene_id) in SOURCES.items():
            if source_type == "tci":
                tci_path = SOURCE / grid / "tci" / f"HGZ_{grid}_TCI_{date}.tif"
                tci = tifffile.imread(tci_path)
                if tci.ndim != 3:
                    raise ValueError(f"Unexpected TCI shape for {tci_path}: {tci.shape}")
                if tci.shape[0] == 3:
                    tci = np.moveaxis(tci, 0, 2)
                if tci.shape[2] != 3:
                    raise ValueError(f"Unexpected TCI shape for {tci_path}: {tci.shape}")
                valid = np.any(tci > 0, axis=2)
                if not np.any(valid):
                    skipped.append(f"{grid}_{date}: zero-valued source GeoTIFF")
                    continue
                true_color = tci.astype(np.uint8)
                output_valid = valid
                x_min = y_min = 0
                source_width, source_height = tci.shape[1], tci.shape[0]
                false_out = None
                ndvi_out = None
                source_ms4 = tci_path
                source_ndvi = None
            else:
                ms4_path = SOURCE / grid / "ms4" / f"HGZ_{grid}_MS4_{date}.tif"
                ndvi_path = SOURCE / grid / "ndvi" / f"HGZ_{grid}_NDVI_{date}.tif"
                ms4 = tifffile.imread(ms4_path)
                if ms4.ndim != 3 or ms4.shape[2] != 4:
                    raise ValueError(f"Unexpected MS4 shape for {ms4_path}: {ms4.shape}")

                valid = np.any(ms4 > 0, axis=2)
                if not np.any(valid):
                    skipped.append(f"{grid}_{date}: zero-valued source GeoTIFF")
                    continue

                # Remove the padded no-data border added by the OGE batch export.
                y_coords, x_coords = np.where(valid)
                x_min, x_max = int(x_coords.min()), int(x_coords.max()) + 1
                y_min, y_max = int(y_coords.min()), int(y_coords.max()) + 1
                ms4_crop = ms4[y_min:y_max, x_min:x_max]
                ndvi_crop = tifffile.imread(ndvi_path)[y_min:y_max, x_min:x_max]

                # OGE export order is B02, B03, B04, B08.
                true_color = stretch_rgb(ms4_crop[..., [2, 1, 0]])
                output_valid = np.any(ms4_crop > 0, axis=2)
                false_color = stretch_rgb(ms4_crop[..., [3, 2, 1]])
                ndvi_color = colorize_ndvi(ndvi_crop)
                source_width, source_height = ms4.shape[1], ms4.shape[0]
                source_ms4 = ms4_path
                source_ndvi = ndvi_path

            ms4_path = SOURCE / grid / "ms4" / f"HGZ_{grid}_MS4_{date}.tif"
            stem = f"{grid}_{date}"
            rgb_out = image_dir / f"{stem}_RGB.png"
            Image.fromarray(true_color, mode="RGB").save(rgb_out)
            if source_type == "ms4":
                false_out = false_dir / f"{stem}_CIR.png"
                ndvi_out = ndvi_dir / f"{stem}_NDVI.png"
                Image.fromarray(false_color, mode="RGB").save(false_out)
                Image.fromarray(ndvi_color, mode="RGB").save(ndvi_out)

            valid_fraction = float(output_valid.mean())
            brightness = true_color[output_valid].mean(axis=1)

            rows.append(
                {
                    "grid_id": grid,
                    "date": date,
                    "scene_id": scene_id,
                    "source_type": source_type,
                    "label_image": str(rgb_out.relative_to(ROOT)),
                    "false_color_reference": str(false_out.relative_to(ROOT)) if false_out else "",
                    "ndvi_reference": str(ndvi_out.relative_to(ROOT)) if ndvi_out else "",
                    "source_ms4": str(source_ms4.relative_to(ROOT)),
                    "source_ndvi": str(source_ndvi.relative_to(ROOT)) if source_ndvi else "",
                    "width": str(true_color.shape[1]),
                    "height": str(true_color.shape[0]),
                    "source_width": str(source_width),
                    "source_height": str(source_height),
                    "crop_x_offset": str(x_min),
                    "crop_y_offset": str(y_min),
                    "valid_fraction": f"{valid_fraction:.6f}",
                    "brightness_mean": f"{float(brightness.mean()):.3f}",
                    "brightness_std": f"{float(brightness.std()):.3f}",
                    "qc_status": "accepted" if valid_fraction >= 0.95 else "review",
                    "label_status": "unlabeled",
                }
            )

    manifest = OUTPUT / "labelme_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Prepared {len(rows)} label images in {OUTPUT}")
    for item in skipped:
        print(f"SKIPPED: {item}")


if __name__ == "__main__":
    main()
