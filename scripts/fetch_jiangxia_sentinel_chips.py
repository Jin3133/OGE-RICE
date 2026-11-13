"""Fetch verified Sentinel-2 L2A chips for the Jiangxia labeling dataset.

The script reads only the three 5 km windows needed by the experiment from
public cloud-optimized GeoTIFFs. It writes four-band GeoTIFFs (B02/B03/B04/B08)
and NDVI files that are compatible with ``prepare_labelme_images.py``.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.windows import from_bounds as window_from_bounds


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/raw/labeling/source_geotiff"

GRIDS = {
    "JX5K_R03C06": (235000.0, 3325000.0, 240000.0, 3330000.0),
    "JX5K_R07C05": (230000.0, 3345000.0, 235000.0, 3350000.0),
    "JX5K_R10C10": (255000.0, 3360000.0, 260000.0, 3365000.0),
}

SCENES = {
    "20250418": "S2B_50RKU_20250418_0_L2A",
    "20250605": "S2C_50RKU_20250605_0_L2A",
    "20250705": "S2C_50RKU_20250705_0_L2A",
    "20250816": "S2B_50RKU_20250816_0_L2A",
    "20251005": "S2B_50RKU_20251005_0_L2A",
}

BANDS = {"B02": "blue", "B03": "green", "B04": "red", "B08": "nir"}


def asset_url(scene_id: str, band: str) -> str:
    satellite, tile, date, _, _ = scene_id.split("_")
    year, month = date[:4], str(int(date[4:6]))
    return (
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/"
        f"sentinel-s2-l2a-cogs/{tile[:2]}/{tile[2]}/{tile[3:]}/"
        f"{year}/{month}/{scene_id}/{band}.tif"
    )


def read_band(date_token: str, scene_id: str, band: str) -> tuple[str, str, dict[str, np.ndarray]]:
    url = f"/vsicurl/{asset_url(scene_id, band)}"
    chips: dict[str, np.ndarray] = {}
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
        GDAL_HTTP_UNSAFESSL="YES",
        GDAL_HTTP_CONNECTTIMEOUT="30",
        GDAL_HTTP_TIMEOUT="180",
        GDAL_HTTP_MAX_RETRY="6",
        GDAL_HTTP_RETRY_DELAY="2",
        GDAL_HTTP_VERSION="1.1",
        AWS_NO_SIGN_REQUEST="YES",
    ):
        with rasterio.open(url) as src:
            if str(src.crs) != "EPSG:32650":
                raise RuntimeError(f"Unexpected CRS for {scene_id}: {src.crs}")
            for grid_id, bounds in GRIDS.items():
                window = window_from_bounds(*bounds, transform=src.transform)
                chip = src.read(1, window=window)
                if chip.shape != (500, 500):
                    raise RuntimeError(f"Unexpected shape {chip.shape}: {scene_id} {band} {grid_id}")
                if not np.any(chip):
                    raise RuntimeError(f"All-zero chip: {scene_id} {band} {grid_id}")
                chips[grid_id] = chip
    return date_token, band, chips


def main() -> None:
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
    arrays: dict[tuple[str, str, str], np.ndarray] = {}
    jobs = [(d, scene, band) for d, scene in SCENES.items() for band in BANDS]
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(read_band, *job) for job in jobs]
        for future in as_completed(futures):
            date_token, band, chips = future.result()
            for grid_id, chip in chips.items():
                arrays[(grid_id, date_token, band)] = chip
            print(f"OK {date_token} {band}", flush=True)

    manifest = []
    for grid_id, bounds in GRIDS.items():
        ms4_dir = OUTPUT / grid_id / "ms4"
        ndvi_dir = OUTPUT / grid_id / "ndvi"
        ms4_dir.mkdir(parents=True, exist_ok=True)
        ndvi_dir.mkdir(parents=True, exist_ok=True)
        transform = from_bounds(*bounds, width=500, height=500)
        for date_token, scene_id in SCENES.items():
            stack = np.stack([arrays[(grid_id, date_token, b)] for b in BANDS])
            red = stack[2].astype("float32")
            nir = stack[3].astype("float32")
            ndvi = np.divide(nir - red, nir + red, out=np.zeros_like(red), where=(nir + red) != 0)

            ms4_path = ms4_dir / f"HGZ_{grid_id}_MS4_{date_token}.tif"
            ndvi_path = ndvi_dir / f"HGZ_{grid_id}_NDVI_{date_token}.tif"
            profile = {
                "driver": "GTiff", "width": 500, "height": 500,
                "crs": "EPSG:32650", "transform": transform,
                "compress": "deflate", "tiled": True,
            }
            with rasterio.open(ms4_path, "w", count=4, dtype=stack.dtype, **profile) as dst:
                dst.write(stack)
                dst.descriptions = tuple(BANDS)
            with rasterio.open(ndvi_path, "w", count=1, dtype="float32", nodata=-9999.0, **profile) as dst:
                dst.write(ndvi, 1)
                dst.set_band_description(1, "NDVI")

            manifest.append({
                "grid_id": grid_id, "date": date_token, "scene_id": scene_id,
                "ms4": str(ms4_path.relative_to(ROOT)),
                "ndvi": str(ndvi_path.relative_to(ROOT)),
                "valid_fraction": float(np.mean(np.all(stack > 0, axis=0))),
                "ndvi_mean": float(ndvi.mean()),
            })

    (OUTPUT / "verified_source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(manifest)} verified grid-date pairs", flush=True)


if __name__ == "__main__":
    main()
