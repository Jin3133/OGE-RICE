"""Extract an unreferenced outer boundary from a white-background clipped image.

The output is deliberately stored in image pixel coordinates.  It must not be
treated as a geographic boundary until a separate georeferencing step supplies
an affine transform and CRS.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--name", required=True)
    parser.add_argument("--official-area-mu", type=float)
    parser.add_argument("--white-threshold", type=int, default=245)
    parser.add_argument("--simplify-pixels", type=float, default=4.0)
    return parser.parse_args()


def border_connected_background(image: np.ndarray, threshold: int) -> np.ndarray:
    near_white = np.all(image >= threshold, axis=2).astype(np.uint8)
    count, labels = cv2.connectedComponents(near_white, connectivity=8)
    if count <= 1:
        return np.zeros(near_white.shape, dtype=bool)
    border_labels = np.unique(
        np.concatenate((labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]))
    )
    border_labels = border_labels[border_labels != 0]
    return np.isin(labels, border_labels)


def close_ring(points: np.ndarray) -> list[list[float]]:
    coordinates = points.reshape(-1, 2).astype(float).tolist()
    if coordinates[0] != coordinates[-1]:
        coordinates.append(coordinates[0])
    return coordinates


def main() -> None:
    args = parse_args()
    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"image could not be read: {args.image}")

    background = border_connected_background(image, args.white_threshold)
    footprint = (~background).astype(np.uint8) * 255
    footprint = cv2.morphologyEx(
        footprint,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )
    contours, _ = cv2.findContours(footprint, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [contour for contour in contours if cv2.contourArea(contour) >= 100]
    if not contours:
        raise SystemExit("no clipped-image footprint was found")
    contours.sort(key=cv2.contourArea, reverse=True)
    simplified = [
        cv2.approxPolyDP(contour, args.simplify_pixels, True) for contour in contours
    ]

    height, width = footprint.shape
    pixel_area = float(sum(cv2.contourArea(contour) for contour in contours))
    official_area_m2 = (
        args.official_area_mu * 2000.0 / 3.0 if args.official_area_mu is not None else None
    )
    inferred_metres_per_pixel = (
        (official_area_m2 / pixel_area) ** 0.5 if official_area_m2 else None
    )

    geometry = {
        "type": "MultiPolygon",
        "coordinates": [[[point for point in close_ring(contour)]] for contour in simplified],
    }
    feature = {
        "type": "Feature",
        "id": f"unreferenced:{args.name}",
        "geometry": geometry,
        "properties": {
            "name": args.name,
            "boundary_role": "irrigation_district_footprint_candidate",
            "coordinate_space": "image_pixel_top_left",
            "crs": None,
            "georeferenced": False,
            "source_image": str(args.image),
            "image_width_pixels": width,
            "image_height_pixels": height,
            "footprint_area_pixels": pixel_area,
            "official_design_area_mu": args.official_area_mu,
            "official_design_area_square_metres": official_area_m2,
            "area_inferred_metres_per_pixel": inferred_metres_per_pixel,
            "white_threshold": args.white_threshold,
            "simplification_tolerance_pixels": args.simplify_pixels,
            "usage_limit": "Pixel-space draft only; georeference before PostGIS import.",
        },
    }

    args.output_directory.mkdir(parents=True, exist_ok=True)
    stem = args.image.stem
    geojson_path = args.output_directory / f"{stem}.pixel-boundary.geojson"
    mask_path = args.output_directory / f"{stem}.footprint-mask.png"
    preview_path = args.output_directory / f"{stem}.boundary-preview.jpg"
    report_path = args.output_directory / f"{stem}.boundary-report.json"

    geojson_path.write_text(json.dumps(feature, ensure_ascii=False, indent=2), encoding="utf-8")
    cv2.imwrite(str(mask_path), footprint)
    preview = image.copy()
    cv2.drawContours(preview, simplified, -1, (0, 0, 255), 10)
    cv2.imwrite(str(preview_path), preview, [cv2.IMWRITE_JPEG_QUALITY, 90])
    report = {
        "name": args.name,
        "source_image": str(args.image),
        "image_size": [width, height],
        "component_count": len(contours),
        "vertex_count_before_simplification": int(sum(len(c) for c in contours)),
        "vertex_count_after_simplification": int(sum(len(c) for c in simplified)),
        "footprint_area_pixels": pixel_area,
        "footprint_ratio": pixel_area / float(width * height),
        "official_design_area_mu": args.official_area_mu,
        "area_inferred_metres_per_pixel": inferred_metres_per_pixel,
        "georeferenced": False,
        "outputs": {
            "pixel_boundary": str(geojson_path),
            "footprint_mask": str(mask_path),
            "boundary_preview": str(preview_path),
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
