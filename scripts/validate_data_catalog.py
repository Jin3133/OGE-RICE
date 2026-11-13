"""Validate small, version-controlled data catalogs without third-party packages."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_rows(relative_path: str) -> list[dict[str, str]]:
    path = ROOT / relative_path
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def require(row: dict[str, str], fields: tuple[str, ...], context: str) -> None:
    missing = [field for field in fields if not row.get(field, "").strip()]
    if missing:
        raise ValueError(f"{context}: missing {', '.join(missing)}")


def validate_sentinel() -> None:
    rows = read_rows("data/catalog/sentinel2_inventory.csv")
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, start=2):
        context = f"sentinel2_inventory.csv:{index}"
        require(row, ("scene_id", "product_id", "tile_id", "acquisition_date", "analysis_tier"), context)
        date.fromisoformat(row["acquisition_date"])
        cloud_value = row["cloud_percent"].strip()
        if cloud_value:
            cloud = float(cloud_value)
            if not 0 <= cloud <= 100:
                raise ValueError(f"{context}: cloud_percent outside 0..100")
        key = (row["scene_id"], row["product_id"])
        if key in seen:
            raise ValueError(f"{context}: duplicate scene/product")
        seen.add(key)
        expected_tile = row["scene_id"].split("_", 1)[0]
        if row["tile_id"] != expected_tile:
            raise ValueError(f"{context}: tile_id does not match scene_id")


def validate_jiangxia_grid_and_tasks() -> None:
    grids = read_rows("data/catalog/jiangxia_5km_grid.csv")
    grid_ids = {row["grid_id"] for row in grids}
    if len(grids) != 107 or len(grid_ids) != len(grids):
        raise ValueError("jiangxia_5km_grid.csv: expected 107 unique grids")
    for index, row in enumerate(grids, start=2):
        context = f"jiangxia_5km_grid.csv:{index}"
        require(row, ("grid_id", "xmin", "ymin", "xmax", "ymax", "crs"), context)
        if row["crs"] != "EPSG:32650":
            raise ValueError(f"{context}: unexpected CRS")
        ratio = float(row["district_coverage_ratio"])
        if not 0 < ratio <= 1:
            raise ValueError(f"{context}: invalid district coverage ratio")

    tasks = read_rows("data/catalog/jiangxia_s2_processing_tasks.csv")
    if len(tasks) != 535:
        raise ValueError("jiangxia_s2_processing_tasks.csv: expected 535 tasks")
    task_ids: set[str] = set()
    for index, row in enumerate(tasks, start=2):
        context = f"jiangxia_s2_processing_tasks.csv:{index}"
        require(row, ("task_id", "grid_id", "scene_id", "product_id", "output_layer"), context)
        if row["grid_id"] not in grid_ids:
            raise ValueError(f"{context}: unknown grid")
        if row["task_id"] in task_ids:
            raise ValueError(f"{context}: duplicate task")
        task_ids.add(row["task_id"])


def validate_algorithm_dataset() -> None:
    rows = read_rows("data/catalog/jiangxia_algorithm_dataset.csv")
    if len(rows) != 15:
        raise ValueError("jiangxia_algorithm_dataset.csv: expected 15 assets")
    grids = {row["grid_id"] for row in rows}
    dates = {row["date"] for row in rows}
    if len(grids) != 3 or len(dates) != 5:
        raise ValueError("jiangxia_algorithm_dataset.csv: expected 3 grids x 5 dates")
    for index, row in enumerate(rows, start=2):
        context = f"jiangxia_algorithm_dataset.csv:{index}"
        require(row, ("dataset_id", "grid_id", "scene_id", "platform_filename", "status"), context)
        if row["status"] != "export_completed":
            raise ValueError(f"{context}: asset is not export_completed")
        if row["crs"] != "EPSG:32650" or row["resolution_m"] != "10":
            raise ValueError(f"{context}: unexpected spatial configuration")


def validate_parameter_units() -> None:
    rows = read_rows("data/parameters/stage_irrigation_quota.csv")
    for index, row in enumerate(rows, start=2):
        context = f"stage_irrigation_quota.csv:{index}"
        require(row, ("region_code", "crop", "stage_name", "version", "quality_status"), context)
        value = row["quota_m3_per_mu"].strip()
        if value and float(value) < 0:
            raise ValueError(f"{context}: quota must be non-negative")


def main() -> None:
    validate_sentinel()
    validate_jiangxia_grid_and_tasks()
    validate_algorithm_dataset()
    validate_parameter_units()
    print("Data catalog validation passed.")


if __name__ == "__main__":
    main()
