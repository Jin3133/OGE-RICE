"""Acquire 2023 10 m annual land-cover crops as a weak reference mask."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import rasterio
import requests
from acquire_sentinel2_demo import load_grids, read_window
from PIL import Image
from rasterio.transform import from_origin

ASSET_URL = (
    "https://ai4edataeuwest.blob.core.windows.net/io-lulc/"
    "io-annual-lulc-v02/50R_20230101-20240101.tif"
)
SIGN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/sign"
CROP_CLASS = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--grid-catalog",
        type=Path,
        default=Path("../oge-rice/data/catalog/jiangxia_5km_grid.csv"),
    )
    parser.add_argument(
        "--grid-ids",
        nargs="+",
        default=("JX5K_R03C06", "JX5K_R05C04", "JX5K_R07C05", "JX5K_R10C10"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../oge-rice/data/raw/cropland_reference_2023"),
    )
    return parser.parse_args()


def write_raster(path: Path, array: np.ndarray, grid, description: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=1,
        dtype=array.dtype,
        crs="EPSG:32650",
        transform=from_origin(grid.xmin, grid.ymax, 10, 10),
        nodata=0,
        compress="deflate",
        tiled=True,
        blockxsize=256,
        blockysize=256,
    ) as dataset:
        dataset.write(array, 1)
        dataset.set_band_description(1, description)
        dataset.update_tags(
            source="Esri 10m Annual Land Use/Land Cover V2 via Microsoft Planetary Computer",
            reference_year="2023",
            grid_id=grid.grid_id,
            crop_class_value=CROP_CLASS,
            usage="weak_reference_only",
        )


def preview(mask: np.ndarray) -> Image.Image:
    image = np.zeros((*mask.shape, 3), dtype=np.uint8)
    image[mask.astype(bool)] = (247, 190, 45)
    return Image.fromarray(image)


def main() -> None:
    args = parse_args()
    grids = load_grids(args.grid_catalog, set(args.grid_ids))
    signed = requests.get(SIGN_URL, params={"href": ASSET_URL}, timeout=60)
    signed.raise_for_status()
    asset_url = signed.json()["href"]
    records = []
    for grid in grids:
        grid_dir = args.output_dir / grid.grid_id
        lc_path = grid_dir / f"{grid.grid_id}_io_lulc_2023.tif"
        mask_path = grid_dir / f"{grid.grid_id}_crop_weak_reference_2023.tif"
        if lc_path.exists() and mask_path.exists():
            with rasterio.open(mask_path) as dataset:
                crop_mask = dataset.read(1)
            print(f"existing {grid.grid_id}", flush=True)
        else:
            print(f"acquiring {grid.grid_id}", flush=True)
            landcover = read_window(asset_url, grid).astype(np.uint8)
            crop_mask = (landcover == CROP_CLASS).astype(np.uint8)
            write_raster(lc_path, landcover, grid, "2023 annual land-cover class")
            write_raster(mask_path, crop_mask, grid, "Cropland weak reference mask")
            preview(crop_mask).save(grid_dir / f"{grid.grid_id}_crop_weak_reference_2023.png")
        records.append(
            {
                "grid_id": grid.grid_id,
                "reference_year": 2023,
                "crop_fraction": round(float(crop_mask.mean()), 6),
                "crop_area_m2": int(crop_mask.sum() * 100),
                "landcover_path": str(lc_path),
                "crop_mask_path": str(mask_path),
                "quality_status": "weak_reference",
            }
        )
        print(f"  crop fraction={records[-1]['crop_fraction']:.3f}", flush=True)
    inventory = args.output_dir / "inventory.csv"
    with inventory.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(inventory)


if __name__ == "__main__":
    main()
