"""Stateless affine georeferencing API."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter

from oge_main.api.contracts import (
    GeoreferencingFitRequest,
    GeoreferencingFitResponse,
    GeoreferencingQualityReport,
    GeoreferencingResidual,
    Wgs84BoundaryFeature,
)
from oge_main.api.errors import ApiProblem
from oge_main.application import GroundControlPoint, fit_affine_georeferencing

router = APIRouter(prefix="/georeferencing", tags=["georeferencing"])


def _rings(geometry_type: str, coordinates: list[Any]) -> Iterable[list[list[float]]]:
    if geometry_type == "Polygon":
        yield from coordinates
    else:
        for polygon in coordinates:
            yield from polygon


def _transform_boundary(
    geometry_type: str,
    coordinates: list[Any],
    transform_pixels,
) -> dict[str, Any]:
    transformed_rings: list[list[list[float]]] = []
    for ring in _rings(geometry_type, coordinates):
        try:
            pixel_points = [(float(point[0]), float(point[1])) for point in ring]
        except (IndexError, TypeError, ValueError) as error:
            raise ValueError("pixel boundary contains an invalid coordinate") from error
        if len(pixel_points) < 4 or pixel_points[0] != pixel_points[-1]:
            raise ValueError("pixel boundary rings must be closed and contain four positions")
        transformed_rings.append(
            [[longitude, latitude] for longitude, latitude in transform_pixels(pixel_points)]
        )

    if not transformed_rings:
        raise ValueError("pixel boundary must contain at least one ring")
    if geometry_type == "Polygon":
        transformed_coordinates: Any = transformed_rings
    else:
        transformed_coordinates = []
        ring_index = 0
        for polygon in coordinates:
            polygon_ring_count = len(polygon)
            transformed_coordinates.append(
                transformed_rings[ring_index : ring_index + polygon_ring_count]
            )
            ring_index += polygon_ring_count
    return {"type": geometry_type, "coordinates": transformed_coordinates}


@router.post("/fit", response_model=GeoreferencingFitResponse)
def fit_georeferencing(payload: GeoreferencingFitRequest) -> GeoreferencingFitResponse:
    try:
        result = fit_affine_georeferencing(
            [
                GroundControlPoint(
                    point_id=point.point_id,
                    pixel_x=point.pixel_x,
                    pixel_y=point.pixel_y,
                    longitude=point.longitude,
                    latitude=point.latitude,
                )
                for point in payload.control_points
            ],
            projected_crs=payload.projected_crs,
        )
        boundary = None
        if payload.pixel_boundary is not None:
            geometry = _transform_boundary(
                payload.pixel_boundary.type,
                payload.pixel_boundary.coordinates,
                result.transform_pixels,
            )
            boundary = Wgs84BoundaryFeature(
                geometry=geometry,
                properties={
                    "image_id": payload.image_id,
                    "quality_status": "unverified",
                    "georeferencing_method": "affine_least_squares",
                    "projected_crs": result.projected_crs,
                    "rmse_metres": result.rmse_metres,
                },
            )
    except ValueError as error:
        raise ApiProblem(
            422,
            "GEOREFERENCING_FIT_REJECTED",
            str(error),
        ) from error

    return GeoreferencingFitResponse(
        image_id=payload.image_id,
        image_width=payload.image_width,
        image_height=payload.image_height,
        report=GeoreferencingQualityReport(
            projected_crs=result.projected_crs,
            coefficients_easting=list(result.coefficients_easting),
            coefficients_northing=list(result.coefficients_northing),
            control_point_count=result.control_point_count,
            design_matrix_rank=result.design_matrix_rank,
            rmse_metres=result.rmse_metres,
            maximum_error_metres=result.maximum_error_metres,
            residuals=[
                GeoreferencingResidual(
                    point_id=item.point_id,
                    predicted_easting=item.predicted_easting,
                    predicted_northing=item.predicted_northing,
                    residual_easting=item.residual_easting,
                    residual_northing=item.residual_northing,
                    error_metres=item.error_metres,
                )
                for item in result.residuals
            ],
        ),
        boundary=boundary,
    )
