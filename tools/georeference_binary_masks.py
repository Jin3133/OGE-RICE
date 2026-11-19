"""Attach an audited affine georeference to aligned binary PNG masks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import Affine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit-response", type=Path, required=True)
    parser.add_argument("--candidate-mask", type=Path, required=True)
    parser.add_argument("--valid-mask", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def read_binary(path: Path) -> np.ndarray:
    array = np.asarray(Image.open(path).convert("L"))
    values = np.unique(array)
    if not np.isin(values, [0, 1, 255]).all():
        raise ValueError(f"mask must contain only 0, 1 or 255: {path}")
    return (array > 0).astype(np.uint8)


def write_mask(path: Path, array: np.ndarray, transform: Affine, crs: str) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype="uint8",
        crs=crs,
        transform=transform,
        nodata=0,
        compress="deflate",
        predictor=2,
        tiled=True,
        blockxsize=512,
        blockysize=512,
    ) as dataset:
        dataset.write(array, 1)


def main() -> None:
    args = parse_args()
    fit = json.loads(args.fit_response.read_text(encoding="utf-8"))
    report = fit["report"]
    east = report["coefficients_easting"]
    north = report["coefficients_northing"]
    transform = Affine(east[1], east[2], east[0], north[1], north[2], north[0])
    candidate = read_binary(args.candidate_mask)
    valid = read_binary(args.valid_mask)
    if candidate.shape != valid.shape:
        raise ValueError("candidate and valid masks must have identical dimensions")
    excluded_candidate_pixels = int(np.count_nonzero((candidate == 1) & (valid == 0)))
    candidate = candidate & valid

    args.output_directory.mkdir(parents=True, exist_ok=True)
    candidate_output = args.output_directory / "candidate-mask.tif"
    valid_output = args.output_directory / "valid-observation-mask.tif"
    write_mask(candidate_output, candidate, transform, report["projected_crs"])
    write_mask(valid_output, valid, transform, report["projected_crs"])

    boundary = fit.get("boundary")
    if boundary is None:
        raise ValueError("fit response does not contain a transformed boundary")
    boundary_output = args.output_directory / "management-unit.geojson"
    boundary_output.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
                "features": [boundary],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidate_mask": str(candidate_output),
                "valid_observation_mask": str(valid_output),
                "boundary": str(boundary_output),
                "crs": report["projected_crs"],
                "candidate_pixels": int(candidate.sum()),
                "excluded_candidate_pixels": excluded_candidate_pixels,
                "valid_pixels": int(valid.sum()),
                "pixel_area_m2": abs(transform.a * transform.e - transform.b * transform.d),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
