"""Stateless affine georeferencing API."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from uuid import uuid4

import cv2
import numpy as np
import requests
from fastapi import APIRouter, File, Form, UploadFile

from oge_main.api.contracts import (
    GeoreferencingFitRequest,
    GeoreferencingFitResponse,
    GeoreferencingQualityReport,
    GeoreferencingResidual,
    GeoreferencingSuggestionResponse,
    SuggestedGeoreferencingControlPoint,
    Wgs84BoundaryFeature,
)
from oge_main.api.errors import ApiProblem
from oge_main.application import (
    GroundControlPoint,
    fit_affine_georeferencing,
    suggest_control_points,
)

router = APIRouter(prefix="/georeferencing", tags=["georeferencing"])

REFERENCE_EXPORT_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/export"
)


@router.post("/suggest", response_model=GeoreferencingSuggestionResponse)
def suggest_georeferencing_points(
    source_image: UploadFile = File(...),
    west: float = Form(..., ge=-180, le=180),
    south: float = Form(..., ge=-90, le=90),
    east: float = Form(..., ge=-180, le=180),
    north: float = Form(..., ge=-90, le=90),
    maximum_points: int = Form(12, ge=3, le=30),
) -> GeoreferencingSuggestionResponse:
    if west >= east or south >= north:
        raise ApiProblem(422, "INVALID_SEARCH_EXTENT", "search extent is invalid")
    source_bytes = source_image.file.read()
    if not source_bytes:
        raise ApiProblem(422, "EMPTY_SOURCE_IMAGE", "source image is empty")
    try:
        response = requests.get(
            REFERENCE_EXPORT_URL,
            params={
                "bbox": f"{west},{south},{east},{north}",
                "bboxSR": "4326",
                "imageSR": "4326",
                "size": "1800,1400",
                "format": "png32",
                "f": "image",
            },
            timeout=30,
        )
        response.raise_for_status()
        reference_bytes = response.content
        reference = cv2.imdecode(
            np.frombuffer(reference_bytes, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        if reference is None:
            raise ValueError("reference imagery could not be decoded")
        result = suggest_control_points(
            source_bytes, reference_bytes, maximum_points=maximum_points
        )
    except requests.RequestException as error:
        raise ApiProblem(
            502, "REFERENCE_IMAGERY_UNAVAILABLE", "reference imagery is temporarily unavailable"
        ) from error
    except ValueError as error:
        raise ApiProblem(422, "CONTROL_POINT_SUGGESTION_REJECTED", str(error)) from error

    reference_height, reference_width = reference.shape[:2]
    points = [
        SuggestedGeoreferencingControlPoint(
            point_id=f"suggested-{uuid4()}",
            pixel_x=point.pixel_x,
            pixel_y=point.pixel_y,
            longitude=west + point.reference_x / reference_width * (east - west),
            latitude=north - point.reference_y / reference_height * (north - south),
            match_distance=point.match_distance,
        )
        for point in result.points
    ]
    return GeoreferencingSuggestionResponse(
        method=result.method,
        detected_matches=result.detected_matches,
        ransac_inliers=result.ransac_inliers,
        points=points,
    )


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
