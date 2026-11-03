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
        require(row, ("scene_id", "product_id", "tile_id", "acquisition_date"), context)
        date.fromisoformat(row["acquisition_date"])
        cloud = float(row["cloud_percent"])
        if not 0 <= cloud <= 100:
            raise ValueError(f"{context}: cloud_percent outside 0..100")
        key = (row["scene_id"], row["product_id"])
        if key in seen:
            raise ValueError(f"{context}: duplicate scene/product")
        seen.add(key)
        expected_tile = row["scene_id"].split("_", 1)[0]
        if row["tile_id"] != expected_tile:
            raise ValueError(f"{context}: tile_id does not match scene_id")


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
    validate_parameter_units()
    print("Data catalog validation passed.")


if __name__ == "__main__":
    main()
