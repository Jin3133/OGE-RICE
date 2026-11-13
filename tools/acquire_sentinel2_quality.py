"""Acquire SCL layers and create conservative clear-pixel masks for demo imagery."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import rasterio
from acquire_sentinel2_demo import DEFAULT_DATES, load_grids, read_window, search_scene
from rasterio.transform import from_origin

# Sentinel-2 L2A Scene Classification Layer classes kept as valid observations:
# 4 vegetation, 5 non-vegetated, 6 water, 7 unclassified.
CLEAR_CLASSES = (4, 5, 6, 7)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--grid-catalog",
        type=Path,
        default=Path("../oge-rice/data/catalog/jiangxia_algorithm_sample_grids.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../oge-rice/data/raw/sentinel2_demo_ms4"),
    )
    parser.add_argument("--dates", nargs="+", default=list(DEFAULT_DATES))
    parser.add_argument("--grid-ids", nargs="+", default=None)
    return parser.parse_args()


def write_single_band(
    path: Path,
    array: np.ndarray,
    *,
    xmin: float,
    ymax: float,
    resolution: int,
    nodata: int,
    description: str,
    tags: dict,
) -> None:
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
        transform=from_origin(xmin, ymax, resolution, resolution),
        nodata=nodata,
        compress="deflate",
        tiled=True,
        blockxsize=256 if array.shape[1] >= 256 else 128,
        blockysize=256 if array.shape[0] >= 256 else 128,
    ) as dataset:
        dataset.write(array, 1)
        dataset.set_band_description(1, description)
        dataset.update_tags(**tags)


def main() -> None:
    args = parse_args()
    grids = load_grids(args.grid_catalog, set(args.grid_ids) if args.grid_ids else None)
    records = []
    for date in args.dates:
        scene = search_scene(date)
        scl_url = scene["assets"]["scl"]["href"]
        for grid in grids:
            base = args.output_dir / grid.grid_id
            scl_path = base / f"{grid.grid_id}_{date.replace('-', '')}_SCL20m.tif"
            mask_path = base / f"{grid.grid_id}_{date.replace('-', '')}_CLEAR10m.tif"
            if scl_path.exists() and mask_path.exists():
                with rasterio.open(mask_path) as dataset:
                    clear_fraction = float(dataset.read(1).mean())
                print(
                    f"[{date}] {grid.grid_id}: existing quality mask, "
                    f"clear={clear_fraction:.3f}",
                    flush=True,
                )
            else:
                print(f"[{date}] {grid.grid_id}: acquiring SCL", flush=True)
                scl = read_window(scl_url, grid).astype(np.uint8)
                if scl.shape != (250, 250):
                    raise RuntimeError(f"Unexpected SCL shape for {grid.grid_id}: {scl.shape}")
                clear20 = np.isin(scl, CLEAR_CLASSES).astype(np.uint8)
                clear10 = np.repeat(np.repeat(clear20, 2, axis=0), 2, axis=1)
                tags = {
                    "source": "Element 84 Earth Search / Sentinel-2 L2A SCL",
                    "scene_id": scene["id"],
                    "acquisition_date": date,
                    "grid_id": grid.grid_id,
                }
                write_single_band(
                    scl_path,
                    scl,
                    xmin=grid.xmin,
                    ymax=grid.ymax,
                    resolution=20,
                    nodata=0,
                    description="Sentinel-2 Scene Classification Layer",
                    tags=tags,
                )
                write_single_band(
                    mask_path,
                    clear10,
                    xmin=grid.xmin,
                    ymax=grid.ymax,
                    resolution=10,
                    nodata=0,
                    description="Conservative clear-pixel mask",
                    tags={**tags, "clear_classes": "4|5|6|7"},
                )
                clear_fraction = float(clear10.mean())
                print(f"  clear fraction={clear_fraction:.3f}", flush=True)
            records.append(
                {
                    "grid_id": grid.grid_id,
                    "date": date,
                    "scene_id": scene["id"],
                    "scl_path": str(scl_path),
                    "clear_mask_path": str(mask_path),
                    "clear_fraction": round(clear_fraction, 6),
                    "quality_status": "accepted" if clear_fraction >= 0.8 else "review",
                }
            )

    inventory = args.output_dir / "quality_inventory.csv"
    with inventory.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(f"Quality inventory: {inventory}")


if __name__ == "__main__":
    main()
