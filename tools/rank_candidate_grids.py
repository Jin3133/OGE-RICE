"""Create quick-look previews and simple spectral metrics for candidate demo grids."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def stretch_rgb(data: np.ndarray) -> np.ndarray:
    rgb = data[[2, 1, 0]].astype(np.float32)
    output = np.zeros_like(rgb, dtype=np.uint8)
    valid = np.all(data > 0, axis=0)
    for index in range(3):
        values = rgb[index][valid]
        low, high = np.percentile(values, [2, 98])
        scaled = np.clip((rgb[index] - low) / max(high - low, 1), 0, 1)
        output[index] = (scaled * 255).astype(np.uint8)
    return np.moveaxis(output, 0, -1)


def analyze(path: Path) -> tuple[dict, Image.Image]:
    with rasterio.open(path) as dataset:
        data = dataset.read().astype(np.float32)
        tags = dataset.tags()
    _blue, green, red, nir = data
    valid = np.all(data > 0, axis=0)
    ndvi = np.divide(nir - red, nir + red, out=np.zeros_like(nir), where=(nir + red) != 0)
    ndwi = np.divide(green - nir, green + nir, out=np.zeros_like(nir), where=(green + nir) != 0)
    metrics = {
        "grid_id": tags.get("grid_id", path.stem.split("_2025")[0]),
        "date": tags.get("acquisition_date", ""),
        "ndvi_mean": round(float(ndvi[valid].mean()), 5),
        "vegetation_fraction_ndvi_gt_0_45": round(float((ndvi[valid] > 0.45).mean()), 5),
        "high_vegetation_fraction_ndvi_gt_0_65": round(float((ndvi[valid] > 0.65).mean()), 5),
        "water_fraction_ndwi_gt_0_10": round(float((ndwi[valid] > 0.10).mean()), 5),
        "valid_fraction": round(float(valid.mean()), 5),
        "path": str(path),
    }
    image = Image.fromarray(stretch_rgb(data)).resize((400, 400), Image.Resampling.LANCZOS)
    return metrics, image


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir or args.input_dir / "qc"
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(args.input_dir.glob("**/*_MS4.tif"))
    if not paths:
        raise RuntimeError(f"No MS4 GeoTIFFs found under {args.input_dir}")

    records = []
    previews = []
    for path in paths:
        metrics, image = analyze(path)
        records.append(metrics)
        previews.append((metrics, image))

    records.sort(
        key=lambda row: (
            row["vegetation_fraction_ndvi_gt_0_45"]
            - row["water_fraction_ndwi_gt_0_10"]
        ),
        reverse=True,
    )
    ranking = output_dir / "candidate_metrics.csv"
    with ranking.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

    by_id = {row["grid_id"]: image for row, image in previews}
    cell_w, cell_h = 420, 455
    sheet = Image.new("RGB", (cell_w * len(records), cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, row in enumerate(records):
        x = index * cell_w
        sheet.paste(by_id[row["grid_id"]], (x + 10, 10))
        label = (
            f"{row['grid_id']}  veg={row['vegetation_fraction_ndvi_gt_0_45']:.2f}  "
            f"water={row['water_fraction_ndwi_gt_0_10']:.2f}"
        )
        draw.text((x + 10, 418), label, fill="black", font=font)
    contact_sheet = output_dir / "candidate_contact_sheet.png"
    sheet.save(contact_sheet)
    print(ranking)
    print(contact_sheet)


if __name__ == "__main__":
    main()
