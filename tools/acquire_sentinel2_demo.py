"""Acquire small georeferenced Sentinel-2 windows for the Jiangxia demo.

The public source scenes are Cloud Optimized GeoTIFFs.  Instead of downloading
an entire 100 km Sentinel-2 tile for every band, this script fetches only the
compressed TIFF tiles intersecting the selected 5 km analysis grids.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
import requests
import tifffile
from rasterio.transform import from_origin

STAC_SEARCH = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"
TILE_ID = "50RKU"
BANDS = ("blue", "green", "red", "nir")
BAND_NAMES = ("B02", "B03", "B04", "B08")
DEFAULT_DATES = ("2025-04-18", "2025-06-14", "2025-07-07", "2025-08-16", "2025-10-05")


@dataclass(frozen=True)
class Grid:
    grid_id: str
    spatial_stratum: str
    xmin: float
    ymin: float
    xmax: float
    ymax: float


class HTTPRangeReader(io.RawIOBase):
    """Minimal seekable reader backed by HTTP range requests."""

    def __init__(self, url: str, timeout: int = 60):
        self.url = url
        self.timeout = timeout
        self.pos = 0
        self.session = requests.Session()
        response = self.session.get(url, headers={"Range": "bytes=0-0"}, timeout=timeout)
        response.raise_for_status()
        content_range = response.headers.get("Content-Range")
        if not content_range:
            raise RuntimeError(f"Server did not return Content-Range for {url}")
        self.size = int(content_range.rsplit("/", 1)[1])

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.size + offset
        else:
            raise ValueError(f"Unsupported whence: {whence}")
        return self.pos

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = self.size - self.pos
        if size == 0:
            return b""
        start = self.pos
        end = min(self.size - 1, start + size - 1)
        response = self.session.get(
            self.url,
            headers={"Range": f"bytes={start}-{end}"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.content
        self.pos += len(data)
        return data

    def close(self) -> None:
        self.session.close()
        super().close()

    def __len__(self) -> int:
        return self.size


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


def load_grids(path: Path, selected: set[str] | None) -> list[Grid]:
    grids = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if selected and row["grid_id"] not in selected:
                continue
            grids.append(
                Grid(
                    grid_id=row["grid_id"],
                    spatial_stratum=row.get("spatial_stratum") or row.get("grid_role", "candidate"),
                    xmin=float(row["xmin"]),
                    ymin=float(row["ymin"]),
                    xmax=float(row["xmax"]),
                    ymax=float(row["ymax"]),
                )
            )
    if not grids:
        raise RuntimeError("No grids selected")
    return grids


def search_scene(date: str) -> dict:
    payload = {
        "collections": [COLLECTION],
        "bbox": [114.0, 30.0, 114.8, 30.7],
        "datetime": f"{date}T00:00:00Z/{date}T23:59:59Z",
        "limit": 20,
    }
    response = requests.post(STAC_SEARCH, json=payload, timeout=60)
    response.raise_for_status()
    features = response.json().get("features", [])
    candidates = [item for item in features if f"_{TILE_ID}_" in item["id"]]
    if not candidates:
        raise RuntimeError(f"No {TILE_ID} scene found on {date}")
    candidates.sort(key=lambda item: float(item["properties"].get("eo:cloud_cover", 100)))
    return candidates[0]


def geotiff_layout(page: tifffile.TiffPage) -> tuple[float, float, float, float]:
    scale = page.tags["ModelPixelScaleTag"].value
    tie = page.tags["ModelTiepointTag"].value
    return float(tie[3]), float(tie[4]), float(scale[0]), float(scale[1])


def read_window(url: str, grid: Grid) -> np.ndarray:
    reader = HTTPRangeReader(url)
    try:
        with tifffile.TiffFile(reader) as tif:
            page = tif.pages[0]
            left, top, pixel_x, pixel_y = geotiff_layout(page)
            col0 = round((grid.xmin - left) / pixel_x)
            col1 = round((grid.xmax - left) / pixel_x)
            row0 = round((top - grid.ymax) / pixel_y)
            row1 = round((top - grid.ymin) / pixel_y)
            if not (0 <= col0 < col1 <= page.imagewidth and 0 <= row0 < row1 <= page.imagelength):
                raise RuntimeError(f"Grid {grid.grid_id} lies outside source scene")

            result = np.zeros((row1 - row0, col1 - col0), dtype=page.dtype)
            tile_w = page.tilewidth
            tile_h = page.tilelength
            tiles_across = math.ceil(page.imagewidth / tile_w)
            tile_col_start = col0 // tile_w
            tile_col_end = (col1 - 1) // tile_w
            tile_row_start = row0 // tile_h
            tile_row_end = (row1 - 1) // tile_h

            for tile_row in range(tile_row_start, tile_row_end + 1):
                for tile_col in range(tile_col_start, tile_col_end + 1):
                    tile_index = tile_row * tiles_across + tile_col
                    reader.seek(page.dataoffsets[tile_index])
                    encoded = reader.read(page.databytecounts[tile_index])
                    decoded, _, _ = page.decode(encoded, tile_index)
                    tile = decoded[0, :, :, 0]

                    src_x0 = tile_col * tile_w
                    src_y0 = tile_row * tile_h
                    ix0 = max(col0, src_x0)
                    ix1 = min(col1, src_x0 + tile.shape[1])
                    iy0 = max(row0, src_y0)
                    iy1 = min(row1, src_y0 + tile.shape[0])
                    result[iy0 - row0 : iy1 - row0, ix0 - col0 : ix1 - col0] = tile[
                        iy0 - src_y0 : iy1 - src_y0,
                        ix0 - src_x0 : ix1 - src_x0,
                    ]
            return result
    finally:
        reader.close()


def write_stack(path: Path, stack: np.ndarray, grid: Grid, scene: dict, date: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "width": stack.shape[2],
        "height": stack.shape[1],
        "count": stack.shape[0],
        "dtype": stack.dtype,
        "crs": "EPSG:32650",
        "transform": from_origin(grid.xmin, grid.ymax, 10, 10),
        "nodata": 0,
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(stack)
        for index, name in enumerate(BAND_NAMES, start=1):
            dataset.set_band_description(index, name)
        dataset.update_tags(
            source="Element 84 Earth Search / Sentinel-2 L2A COG",
            scene_id=scene["id"],
            acquisition_date=date,
            cloud_percent=scene["properties"].get("eo:cloud_cover"),
            grid_id=grid.grid_id,
            spatial_stratum=grid.spatial_stratum,
            band_order="|".join(BAND_NAMES),
        )


def qc_record(path: Path, grid: Grid, scene: dict, date: str) -> dict:
    with rasterio.open(path) as dataset:
        data = dataset.read()
        valid = np.all(data > 0, axis=0)
        return {
            "dataset_id": f"JXMS4_{grid.grid_id.removeprefix('JX5K_')}_{date.replace('-', '')}",
            "grid_id": grid.grid_id,
            "spatial_stratum": grid.spatial_stratum,
            "date": date,
            "scene_id": scene["id"],
            "cloud_percent": scene["properties"].get("eo:cloud_cover"),
            "band_order": "|".join(BAND_NAMES),
            "crs": str(dataset.crs),
            "resolution_m": abs(dataset.transform.a),
            "width": dataset.width,
            "height": dataset.height,
            "valid_fraction": round(float(valid.mean()), 6),
            "min_value": int(data[:, valid].min()) if valid.any() else 0,
            "max_value": int(data[:, valid].max()) if valid.any() else 0,
            "local_path": str(path),
            "status": "accepted" if valid.mean() >= 0.95 else "review",
        }


def main() -> None:
    args = parse_args()
    grids = load_grids(args.grid_catalog, set(args.grid_ids) if args.grid_ids else None)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    scenes = {}
    for date in args.dates:
        scene = search_scene(date)
        scenes[date] = {
            "scene_id": scene["id"],
            "cloud_percent": scene["properties"].get("eo:cloud_cover"),
            "assets": {name: scene["assets"][name]["href"] for name in BANDS},
        }
        for grid in grids:
            path = args.output_dir / grid.grid_id / f"{grid.grid_id}_{date.replace('-', '')}_MS4.tif"
            if path.exists():
                try:
                    existing = qc_record(path, grid, scene, date)
                    if existing["width"] == 500 and existing["height"] == 500:
                        records.append(existing)
                        print(
                            f"[{date}] {grid.grid_id}: existing file accepted, "
                            f"valid={existing['valid_fraction']:.3f}",
                            flush=True,
                        )
                        continue
                except rasterio.errors.RasterioError:
                    pass
            print(f"[{date}] {grid.grid_id}: acquiring {path.name}", flush=True)
            with ThreadPoolExecutor(max_workers=len(BANDS)) as executor:
                futures = [
                    executor.submit(read_window, scene["assets"][band]["href"], grid)
                    for band in BANDS
                ]
                arrays = [future.result() for future in futures]
            stack = np.stack(arrays, axis=0)
            write_stack(path, stack, grid, scene, date)
            records.append(qc_record(path, grid, scene, date))
            print(
                f"  accepted: {stack.shape}, valid={records[-1]['valid_fraction']:.3f}",
                flush=True,
            )

    inventory = args.output_dir / "inventory.csv"
    with inventory.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    (args.output_dir / "source_scenes.json").write_text(
        json.dumps(scenes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(records)} datasets to {args.output_dir}")
    print(f"Inventory: {inventory}")


if __name__ == "__main__":
    main()
