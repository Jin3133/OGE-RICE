"""Prepare a compact multi-temporal LabelMe package for rice annotation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont

CANONICAL_DATE = "20250707"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("../oge-rice/data/raw/sentinel2_demo_ms4"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../oge-rice/data/raw/labeling/labelme_rice_v1"),
    )
    return parser.parse_args()


def stretch(channels: np.ndarray, valid: np.ndarray) -> np.ndarray:
    output = np.zeros_like(channels, dtype=np.uint8)
    for index in range(channels.shape[0]):
        values = channels[index][valid]
        low, high = np.percentile(values, [2, 98])
        scaled = np.clip((channels[index] - low) / max(high - low, 1), 0, 1)
        output[index] = (scaled * 255).astype(np.uint8)
    return np.moveaxis(output, 0, -1)


def make_visuals(data: np.ndarray) -> tuple[Image.Image, Image.Image, Image.Image]:
    valid = np.all(data > 0, axis=0)
    blue, green, red, nir = data.astype(np.float32)
    rgb = Image.fromarray(stretch(np.stack([red, green, blue]), valid))
    cir = Image.fromarray(stretch(np.stack([nir, red, green]), valid))
    ndvi = np.divide(nir - red, nir + red, out=np.zeros_like(nir), where=(nir + red) != 0)
    ndvi_scaled = np.clip((ndvi + 0.2) / 1.0, 0, 1)
    ndvi_rgb = np.zeros((*ndvi.shape, 3), dtype=np.uint8)
    ndvi_rgb[..., 0] = (255 * np.clip(1.5 - ndvi_scaled * 2, 0, 1)).astype(np.uint8)
    ndvi_rgb[..., 1] = (255 * np.clip(ndvi_scaled * 1.5, 0, 1)).astype(np.uint8)
    ndvi_rgb[..., 2] = (120 * np.clip(1 - ndvi_scaled, 0, 1)).astype(np.uint8)
    ndvi_rgb[~valid] = 0
    return rgb, cir, Image.fromarray(ndvi_rgb)


def empty_labelme_json(image_name: str, width: int, height: int, grid_id: str) -> dict:
    return {
        "version": "5.6.0",
        "flags": {
            "annotation_status_unreviewed": True,
            "verified_empty": False,
        },
        "otherData": {
            "grid_id": grid_id,
            "canonical_date": "2025-07-07",
        },
        "shapes": [],
        "imagePath": image_name,
        "imageData": None,
        "imageHeight": height,
        "imageWidth": width,
    }


def create_contact_sheet(
    grid_id: str,
    dated_visuals: list[tuple[str, Image.Image, Image.Image, Image.Image]],
    output: Path,
) -> None:
    thumb = 300
    label_h = 34
    margin = 10
    width = margin + len(dated_visuals) * (thumb + margin)
    height = margin + 3 * (thumb + label_h + margin)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    row_names = ("RGB", "CIR", "NDVI")
    for col, (date, rgb, cir, ndvi) in enumerate(dated_visuals):
        for row, image in enumerate((rgb, cir, ndvi)):
            x = margin + col * (thumb + margin)
            y = margin + row * (thumb + label_h + margin)
            sheet.paste(image.resize((thumb, thumb), Image.Resampling.LANCZOS), (x, y))
            draw.text((x, y + thumb + 7), f"{grid_id} {date} {row_names[row]}", fill="black", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)


def main() -> None:
    args = parse_args()
    tasks_dir = args.output_dir / "tasks"
    rgb_dir = args.output_dir / "references" / "rgb"
    cir_dir = args.output_dir / "references" / "cir"
    ndvi_dir = args.output_dir / "references" / "ndvi"
    sheet_dir = args.output_dir / "references" / "contact_sheets"
    for directory in (tasks_dir, rgb_dir, cir_dir, ndvi_dir, sheet_dir):
        directory.mkdir(parents=True, exist_ok=True)

    tiffs = sorted(args.input_dir.glob("JX5K_*/*_MS4.tif"))
    by_grid: dict[str, list[Path]] = {}
    for path in tiffs:
        grid_id = path.parent.name
        by_grid.setdefault(grid_id, []).append(path)

    manifest_rows = []
    for grid_id, paths in sorted(by_grid.items()):
        dated_visuals = []
        canonical = None
        canonical_meta = None
        for path in sorted(paths):
            date = path.stem.split("_")[-2]
            with rasterio.open(path) as dataset:
                data = dataset.read()
                bounds = dataset.bounds
                transform = dataset.transform
                crs = str(dataset.crs)
            rgb, cir, ndvi = make_visuals(data)
            name = f"{grid_id}_{date}"
            rgb.save(rgb_dir / f"{name}_RGB.png")
            cir.save(cir_dir / f"{name}_CIR.png")
            ndvi.save(ndvi_dir / f"{name}_NDVI.png")
            dated_visuals.append((date, rgb, cir, ndvi))
            if date == CANONICAL_DATE:
                canonical = rgb
                canonical_meta = (path, bounds, transform, crs)

        if canonical is None or canonical_meta is None:
            raise RuntimeError(f"Missing canonical date for {grid_id}")
        image_name = f"{grid_id}_{CANONICAL_DATE}_RGB.png"
        canonical.save(tasks_dir / image_name)
        label_path = tasks_dir / image_name.replace(".png", ".json")
        if not label_path.exists():
            label_path.write_text(
                json.dumps(
                    empty_labelme_json(image_name, canonical.width, canonical.height, grid_id),
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        source_path, bounds, transform, crs = canonical_meta
        manifest_rows.append(
            {
                "grid_id": grid_id,
                "annotation_image": str(tasks_dir / image_name),
                "label_json": str(label_path),
                "source_geotiff": str(source_path),
                "canonical_date": "2025-07-07",
                "crs": crs,
                "xmin": bounds.left,
                "ymin": bounds.bottom,
                "xmax": bounds.right,
                "ymax": bounds.top,
                "pixel_size_x": transform.a,
                "pixel_size_y": abs(transform.e),
                "width": canonical.width,
                "height": canonical.height,
                "label_status": "unlabeled",
            }
        )
        create_contact_sheet(
            grid_id,
            dated_visuals,
            sheet_dir / f"{grid_id}_five_dates_rgb_cir_ndvi.png",
        )

    manifest = args.output_dir / "labelme_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)
    print(f"Prepared {len(manifest_rows)} LabelMe tasks")
    print(tasks_dir)
    print(manifest)


if __name__ == "__main__":
    main()
