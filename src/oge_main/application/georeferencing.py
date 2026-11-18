"""Auditable affine georeferencing for unreferenced raster imagery."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite, sqrt

import numpy as np
from rasterio.crs import CRS
from rasterio.warp import transform


@dataclass(frozen=True, slots=True)
class GroundControlPoint:
    point_id: str
    pixel_x: float
    pixel_y: float
    longitude: float
    latitude: float


@dataclass(frozen=True, slots=True)
class ControlPointResidual:
    point_id: str
    predicted_easting: float
    predicted_northing: float
    residual_easting: float
    residual_northing: float
    error_metres: float


@dataclass(frozen=True, slots=True)
class AffineGeoreferencingResult:
    coefficients_easting: tuple[float, float, float]
    coefficients_northing: tuple[float, float, float]
    projected_crs: str
    residuals: tuple[ControlPointResidual, ...]
    rmse_metres: float
    maximum_error_metres: float
    control_point_count: int
    design_matrix_rank: int

    def transform_pixels(
        self, coordinates: Iterable[tuple[float, float]]
    ) -> list[tuple[float, float]]:
        points = list(coordinates)
        if not points:
            return []
        matrix = np.asarray([[1.0, x, y] for x, y in points], dtype=np.float64)
        eastings = matrix @ np.asarray(self.coefficients_easting)
        northings = matrix @ np.asarray(self.coefficients_northing)
        longitudes, latitudes = transform(
            self.projected_crs,
            "EPSG:4326",
            eastings.tolist(),
            northings.tolist(),
        )
        return list(zip(longitudes, latitudes, strict=True))


def fit_affine_georeferencing(
    control_points: Iterable[GroundControlPoint],
    *,
    projected_crs: str = "EPSG:32651",
) -> AffineGeoreferencingResult:
    """Fit a pixel-to-map affine transform and report residuals in metres."""

    points = tuple(control_points)
    if len(points) < 3:
        raise ValueError("at least three control points are required")
    if len({point.point_id for point in points}) != len(points):
        raise ValueError("control point identifiers must be unique")
    values = (
        value
        for point in points
        for value in (point.pixel_x, point.pixel_y, point.longitude, point.latitude)
    )
    if not all(isfinite(value) for value in values):
        raise ValueError("control point coordinates must be finite")
    pixel_pairs = {(point.pixel_x, point.pixel_y) for point in points}
    map_pairs = {(point.longitude, point.latitude) for point in points}
    if len(pixel_pairs) != len(points) or len(map_pairs) != len(points):
        raise ValueError("control points must not contain duplicate source or target positions")

    try:
        target_crs = CRS.from_user_input(projected_crs)
    except Exception as error:
        raise ValueError(f"invalid projected CRS: {projected_crs}") from error
    if not target_crs.is_projected:
        raise ValueError("georeferencing fit requires a projected target CRS")

    design = np.asarray(
        [[1.0, point.pixel_x, point.pixel_y] for point in points], dtype=np.float64
    )
    rank = int(np.linalg.matrix_rank(design))
    if rank < 3:
        raise ValueError("source control points must not be collinear")

    eastings, northings = transform(
        "EPSG:4326",
        target_crs,
        [point.longitude for point in points],
        [point.latitude for point in points],
    )
    target_easting = np.asarray(eastings, dtype=np.float64)
    target_northing = np.asarray(northings, dtype=np.float64)
    coefficients_easting = np.linalg.lstsq(design, target_easting, rcond=None)[0]
    coefficients_northing = np.linalg.lstsq(design, target_northing, rcond=None)[0]
    predicted_easting = design @ coefficients_easting
    predicted_northing = design @ coefficients_northing

    residuals: list[ControlPointResidual] = []
    squared_errors: list[float] = []
    for index, point in enumerate(points):
        residual_easting = float(predicted_easting[index] - target_easting[index])
        residual_northing = float(predicted_northing[index] - target_northing[index])
        error_metres = sqrt(residual_easting**2 + residual_northing**2)
        squared_errors.append(error_metres**2)
        residuals.append(
            ControlPointResidual(
                point_id=point.point_id,
                predicted_easting=float(predicted_easting[index]),
                predicted_northing=float(predicted_northing[index]),
                residual_easting=residual_easting,
                residual_northing=residual_northing,
                error_metres=error_metres,
            )
        )

    return AffineGeoreferencingResult(
        coefficients_easting=tuple(float(value) for value in coefficients_easting),
        coefficients_northing=tuple(float(value) for value in coefficients_northing),
        projected_crs=target_crs.to_string(),
        residuals=tuple(residuals),
        rmse_metres=sqrt(sum(squared_errors) / len(squared_errors)),
        maximum_error_metres=max(sqrt(value) for value in squared_errors),
        control_point_count=len(points),
        design_matrix_rank=rank,
    )
