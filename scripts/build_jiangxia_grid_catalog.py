"""Build the Jiangxia 5 km analysis grid and scene-by-grid processing catalog.

The script intentionally uses only Python's standard library so the catalog can be
rebuilt in the competition environment without GIS desktop dependencies.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY = ROOT / "data/boundaries/jiangxia_420115_utm50n.geojson"
GRID_GEOJSON = ROOT / "data/grids/jiangxia_5km_grid_utm50n.geojson"
GRID_CSV = ROOT / "data/catalog/jiangxia_5km_grid.csv"
TASK_CSV = ROOT / "data/catalog/jiangxia_s2_processing_tasks.csv"
SCENE_CSV = ROOT / "data/catalog/sentinel2_inventory.csv"
CELL_SIZE = 5_000
SAMPLE_STEP = 250


def point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            cross_x = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < cross_x:
                inside = not inside
        j = i
    return inside


def point_in_boundary(x: float, y: float, polygons: list) -> bool:
    for polygon in polygons:
        if not point_in_ring(x, y, polygon[0]):
            continue
        if any(point_in_ring(x, y, hole) for hole in polygon[1:]):
            continue
        return True
    return False


def approximate_coverage(x0: int, y0: int, polygons: list) -> float:
    inside = 0
    total = 0
    offset = SAMPLE_STEP / 2
    x = x0 + offset
    while x < x0 + CELL_SIZE:
        y = y0 + offset
        while y < y0 + CELL_SIZE:
            total += 1
            inside += point_in_boundary(x, y, polygons)
            y += SAMPLE_STEP
        x += SAMPLE_STEP
    return inside / total


def main() -> None:
    boundary = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    polygons = boundary["features"][0]["geometry"]["coordinates"]
    points = [point for polygon in polygons for ring in polygon for point in ring]
    min_x = int(min(p[0] for p in points) // CELL_SIZE * CELL_SIZE)
    max_x = int(max(p[0] for p in points) // CELL_SIZE * CELL_SIZE)
    min_y = int(min(p[1] for p in points) // CELL_SIZE * CELL_SIZE)
    max_y = int(max(p[1] for p in points) // CELL_SIZE * CELL_SIZE)

    rows: list[dict[str, str]] = []
    features = []
    row_index = 1
    for y0 in range(min_y, max_y + CELL_SIZE, CELL_SIZE):
        col_index = 1
        for x0 in range(min_x, max_x + CELL_SIZE, CELL_SIZE):
            ratio = approximate_coverage(x0, y0, polygons)
            if ratio < 0.01:
                col_index += 1
                continue
            grid_id = f"JX5K_R{row_index:02d}C{col_index:02d}"
            ring = [[x0, y0], [x0 + CELL_SIZE, y0], [x0 + CELL_SIZE, y0 + CELL_SIZE],
                    [x0, y0 + CELL_SIZE], [x0, y0]]
            quality = "core" if ratio >= 0.5 else "edge"
            row = {
                "grid_id": grid_id,
                "xmin": str(x0),
                "ymin": str(y0),
                "xmax": str(x0 + CELL_SIZE),
                "ymax": str(y0 + CELL_SIZE),
                "center_x": f"{x0 + CELL_SIZE / 2:.1f}",
                "center_y": f"{y0 + CELL_SIZE / 2:.1f}",
                "district_coverage_ratio": f"{ratio:.4f}",
                "grid_role": quality,
                "crs": "EPSG:32650",
            }
            rows.append(row)
            features.append({
                "type": "Feature",
                "properties": row,
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            })
            col_index += 1
        row_index += 1

    GRID_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    GRID_GEOJSON.write_text(json.dumps({
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32650"}},
        "features": features,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    with GRID_CSV.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    with SCENE_CSV.open(encoding="utf-8-sig", newline="") as source:
        scenes = list(csv.DictReader(source))
    accepted = [s for s in scenes if s["analysis_tier"] in {"core", "supplement"}]
    fields = ["task_id", "grid_id", "scene_id", "product_id", "acquisition_date",
              "season_stage", "analysis_tier", "operation", "output_layer", "status",
              "result_path"]
    with TASK_CSV.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        for grid in rows:
            for scene in accepted:
                token = scene["acquisition_date"].replace("-", "")
                task_id = f"{grid['grid_id']}_{token}"
                exported = task_id == "JX5K_R07C05_20251005"
                status = "export_completed" if exported else "planned"
                writer.writerow({
                    "task_id": task_id,
                    "grid_id": grid["grid_id"],
                    "scene_id": scene["scene_id"],
                    "product_id": scene["product_id"],
                    "acquisition_date": scene["acquisition_date"],
                    "season_stage": scene["season_stage"],
                    "analysis_tier": scene["analysis_tier"],
                    "operation": "clip+B08_B04_NDVI",
                    "output_layer": f"HGZ_{grid['grid_id']}_NDVI_{token}",
                    "status": status,
                    "result_path": (
                        "myData/批处理结果/HGZ_JX5K_R07C05_NDVI_20251005.tif.tif"
                        if exported else ""
                    ),
                })

    print(f"Generated {len(rows)} grids and {len(rows) * len(accepted)} processing tasks")


if __name__ == "__main__":
    main()
