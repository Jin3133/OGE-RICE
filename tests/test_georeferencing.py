from __future__ import annotations

import pytest
from rasterio.warp import transform

from oge_main.application import GroundControlPoint, fit_affine_georeferencing


def make_point(point_id: str, x: float, y: float) -> GroundControlPoint:
    # Known affine mapping in EPSG:32651; convert targets to WGS 84 for the public input.
    easting = 350_000.0 + 1.4 * x + 0.08 * y
    northing = 3_535_000.0 - 0.03 * x - 1.35 * y
    longitude, latitude = transform("EPSG:32651", "EPSG:4326", [easting], [northing])
    return GroundControlPoint(point_id, x, y, longitude[0], latitude[0])


def test_fits_known_affine_transform_and_transforms_pixels() -> None:
    points = [
        make_point("north-west", 100, 100),
        make_point("north-east", 7000, 200),
        make_point("south-west", 200, 8000),
        make_point("south-east", 7200, 8200),
        make_point("centre", 4000, 4500),
    ]

    result = fit_affine_georeferencing(points)

    assert result.control_point_count == 5
    assert result.design_matrix_rank == 3
    assert result.coefficients_easting == pytest.approx((350_000, 1.4, 0.08), abs=1e-6)
    assert result.coefficients_northing == pytest.approx((3_535_000, -0.03, -1.35), abs=1e-6)
    assert result.rmse_metres < 1e-6
    assert result.maximum_error_metres < 1e-6

    longitude, latitude = result.transform_pixels([(100, 100)])[0]
    assert longitude == pytest.approx(points[0].longitude, abs=1e-10)
    assert latitude == pytest.approx(points[0].latitude, abs=1e-10)


def test_rejects_fewer_than_three_points() -> None:
    with pytest.raises(ValueError, match="at least three"):
        fit_affine_georeferencing([make_point("one", 0, 0), make_point("two", 1, 1)])


def test_rejects_collinear_source_points() -> None:
    points = [make_point("one", 0, 0), make_point("two", 1, 1), make_point("three", 2, 2)]
    with pytest.raises(ValueError, match="must not be collinear"):
        fit_affine_georeferencing(points)


def test_rejects_duplicate_source_positions() -> None:
    points = [make_point("one", 0, 0), make_point("two", 0, 0), make_point("three", 0, 2)]
    with pytest.raises(ValueError, match="duplicate source or target"):
        fit_affine_georeferencing(points)


def test_rejects_geographic_fit_crs() -> None:
    points = [make_point("one", 0, 0), make_point("two", 1, 0), make_point("three", 0, 1)]
    with pytest.raises(ValueError, match="requires a projected"):
        fit_affine_georeferencing(points, projected_crs="EPSG:4326")
