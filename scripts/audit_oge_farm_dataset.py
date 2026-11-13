#!/usr/bin/env python3
"""Audit the downloaded OGE Wuhan-1 cropland segmentation dataset."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import rasterio


ROOT = Path(__file__).resolve().parents[1]
DATASET = (
    ROOT
    / "data/raw/oge_wuhan1_farm/extracted"
    / "89d279976ef74625a1ea00d6cad512c1_farm"
)
OUTPUT = ROOT / "data/catalog/oge_wuhan1_farm_audit.csv"


def main() -> None:
    images = DATASET / "train/images"
    masks = DATASET / "train/masks"
    image_paths = {p.stem: p for p in images.glob("*.tif")}
    mask_paths = {p.stem: p for p in masks.glob("*.tif")}
    keys = sorted(image_paths.keys() | mask_paths.keys(), key=lambda x: int(x[3:]))

    rows: list[dict[str, object]] = []
    for key in keys:
        image_path = image_paths.get(key)
        mask_path = mask_paths.get(key)
        row: dict[str, object] = {
            "sample_id": key,
            "image_exists": image_path is not None,
            "mask_exists": mask_path is not None,
        }
        if image_path and mask_path:
            with rasterio.open(image_path) as src:
                image = src.read()
                row.update(
                    image_width=src.width,
                    image_height=src.height,
                    image_bands=src.count,
                    image_dtype=src.dtypes[0],
                    image_min=int(image.min()),
                    image_max=int(image.max()),
                )
            with rasterio.open(mask_path) as src:
                mask = src.read(1)
                values = np.unique(mask)
                row.update(
                    mask_width=src.width,
                    mask_height=src.height,
                    mask_bands=src.count,
                    mask_dtype=src.dtypes[0],
                    mask_values="|".join(map(str, values.tolist())),
                    farm_fraction=float(np.mean(mask != 0)),
                )
            row["shape_match"] = image.shape[1:] == mask.shape
            row["qc_status"] = (
                "accepted"
                if image.shape == (3, 512, 512)
                and mask.shape == (512, 512)
                and set(values.tolist()).issubset({0, 1})
                else "review"
            )
        else:
            row["qc_status"] = "missing_pair"
        rows.append(row)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "sample_id",
        "image_exists",
        "mask_exists",
        "image_width",
        "image_height",
        "image_bands",
        "image_dtype",
        "image_min",
        "image_max",
        "mask_width",
        "mask_height",
        "mask_bands",
        "mask_dtype",
        "mask_values",
        "farm_fraction",
        "shape_match",
        "qc_status",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    accepted = sum(row["qc_status"] == "accepted" for row in rows)
    print(f"samples={len(rows)} accepted={accepted} output={OUTPUT}")


if __name__ == "__main__":
    main()
