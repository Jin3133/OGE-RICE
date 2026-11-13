"""Download three missing Sentinel-2 true-colour COGs and crop grid chips."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

import requests
import rasterio
from rasterio.transform import from_bounds
from rasterio.windows import from_bounds as window_from_bounds


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/raw/labeling/source_geotiff/_scene_cache"
OUTPUT = ROOT / "data/raw/labeling/source_geotiff"

GRIDS = {
    "JX5K_R03C06": (235000.0, 3325000.0, 240000.0, 3330000.0),
    "JX5K_R07C05": (230000.0, 3345000.0, 235000.0, 3350000.0),
    "JX5K_R10C10": (255000.0, 3360000.0, 260000.0, 3365000.0),
}
SCENES = {
    "20250418": "S2B_50RKU_20250418_0_L2A",
    "20250614": "S2A_50RKU_20250614_0_L2A",
    "20250707": "S2B_50RKU_20250707_0_L2A",
}


def url(scene_id: str) -> str:
    date = scene_id.split("_")[2]
    return (
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/"
        f"sentinel-s2-l2a-cogs/50/R/KU/{date[:4]}/{int(date[4:6])}/"
        f"{scene_id}/TCI.tif"
    )


def download(date_token: str, scene_id: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"{scene_id}_TCI.tif"
    if target.exists() and target.stat().st_size > 1_000_000:
        return target
    partial = target.with_suffix(".part")
    source_url = url(scene_id)
    expected = int(requests.head(source_url, timeout=30).headers["content-length"])
    for attempt in range(8):
        downloaded = partial.stat().st_size if partial.exists() else 0
        if downloaded == expected:
            break
        headers = {"Range": f"bytes={downloaded}-"} if downloaded else {}
        try:
            with requests.get(
                source_url, headers=headers, stream=True, timeout=(30, 300)
            ) as response:
                response.raise_for_status()
                if downloaded and response.status_code != 206:
                    downloaded = 0
                    mode = "wb"
                else:
                    mode = "ab" if downloaded else "wb"
                with partial.open(mode) as handle:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            handle.write(chunk)
        except requests.RequestException as exc:
            print(f"retry {date_token} {attempt + 1}: {exc}", flush=True)
            time.sleep(min(2 ** attempt, 20))
    if not partial.exists() or partial.stat().st_size != expected:
        actual = partial.stat().st_size if partial.exists() else 0
        raise RuntimeError(f"Incomplete download {date_token}: {actual}/{expected}")
    partial.replace(target)
    print(f"downloaded {date_token} {target.stat().st_size / 1e6:.1f} MB", flush=True)
    return target


def crop(date_token: str, source: Path) -> None:
    with rasterio.open(source) as src:
        if src.count != 3 or str(src.crs) != "EPSG:32650":
            raise RuntimeError(f"Unexpected TCI metadata: {source} {src.count} {src.crs}")
        for grid_id, bounds in GRIDS.items():
            window = window_from_bounds(*bounds, transform=src.transform)
            data = src.read(window=window)
            if data.shape != (3, 500, 500) or not data.any():
                raise RuntimeError(f"Invalid chip {grid_id} {date_token}: {data.shape}")
            folder = OUTPUT / grid_id / "tci"
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"HGZ_{grid_id}_TCI_{date_token}.tif"
            with rasterio.open(
                target, "w", driver="GTiff", width=500, height=500, count=3,
                dtype=data.dtype, crs="EPSG:32650",
                transform=from_bounds(*bounds, width=500, height=500),
                compress="deflate", tiled=True,
            ) as dst:
                dst.write(data)
                dst.descriptions = ("red", "green", "blue")
            print(f"cropped {grid_id} {date_token}", flush=True)


def main() -> None:
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {d: pool.submit(download, d, scene) for d, scene in SCENES.items()}
        paths = {d: future.result() for d, future in futures.items()}
    for date_token, source in paths.items():
        crop(date_token, source)


if __name__ == "__main__":
    main()
