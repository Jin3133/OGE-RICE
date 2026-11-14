"""Spatial area statistics for versioned candidate-mask results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from pydantic import BaseModel, ConfigDict
from rasterio.crs import CRS
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom

from oge_main.domain.models import (
    AreaStatistic,
    DataQuality,
    VersionedReference,
    VersionInfo,
)


@dataclass(frozen=True, slots=True)
class SpatialStatisticsCommand:
    """All explicit inputs required to create one area-statistic version."""

    statistic_id: str
    management_unit: VersionedReference
    remote_sensing_result: VersionedReference
    candidate_mask_path: Path
    valid_observation_mask_path: Path
    boundary_path: Path
    calculated_at: datetime
    quality: DataQuality
    version: VersionInfo


class SpatialStatisticsJob(BaseModel):
    """Portable JSON contract for a local or queued spatial-statistics job."""

    model_config = ConfigDict(extra="forbid")

    statistic_id: str
    management_unit: VersionedReference
    remote_sensing_result: VersionedReference
    candidate_mask_path: Path
    valid_observation_mask_path: Path
    boundary_path: Path
    calculated_at: datetime
    quality: DataQuality
    version: VersionInfo

    def to_command(self, *, base_directory: Path) -> SpatialStatisticsCommand:
        def resolve(path: Path) -> Path:
            return path if path.is_absolute() else base_directory / path

        return SpatialStatisticsCommand(
            statistic_id=self.statistic_id,
            management_unit=self.management_unit,
            remote_sensing_result=self.remote_sensing_result,
            candidate_mask_path=resolve(self.candidate_mask_path),
            valid_observation_mask_path=resolve(self.valid_observation_mask_path),
            boundary_path=resolve(self.boundary_path),
            calculated_at=self.calculated_at,
            quality=self.quality,
            version=self.version,
        )


def _load_boundary(path: Path) -> tuple[list[dict[str, Any]], CRS]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("type") == "FeatureCollection":
        geometries = [
            feature.get("geometry")
            for feature in document.get("features", [])
            if feature.get("geometry")
        ]
    elif document.get("type") == "Feature":
        geometries = [document.get("geometry")]
    else:
        geometries = [document]
    if not geometries or any(geometry is None for geometry in geometries):
        raise ValueError("boundary must contain at least one geometry")

    crs_value: str | None = None
    crs_object = document.get("crs")
    if isinstance(crs_object, dict):
        properties = crs_object.get("properties", {})
        crs_value = properties.get("name")
    if not crs_value:
        raise ValueError("boundary GeoJSON must declare its CRS explicitly")
    try:
        boundary_crs = CRS.from_user_input(crs_value)
    except Exception as error:  # rasterio normalizes several CRS exception types
        raise ValueError(f"invalid boundary CRS: {crs_value}") from error
    return geometries, boundary_crs


def _require_binary(array: np.ndarray, *, name: str) -> None:
    values = np.unique(array)
    if not np.isin(values, [0, 1]).all():
        raise ValueError(f"{name} must be binary with values 0 and 1")


def _require_aligned(candidate: rasterio.io.DatasetReader, valid: rasterio.io.DatasetReader) -> None:
    if candidate.crs != valid.crs:
        raise ValueError("candidate and valid-observation masks must use the same CRS")
    if candidate.transform != valid.transform:
        raise ValueError("candidate and valid-observation masks must use the same transform")
    if candidate.width != valid.width or candidate.height != valid.height:
        raise ValueError("candidate and valid-observation masks must use the same dimensions")


def _pixel_area_square_metres(dataset: rasterio.io.DatasetReader) -> float:
    if dataset.crs is None or not dataset.crs.is_projected:
        raise ValueError("area statistics require a projected raster CRS")
    unit_name, unit_factor = dataset.crs.linear_units_factor
    if unit_factor <= 0:
        raise ValueError(f"invalid projected linear unit: {unit_name}")
    determinant = abs(
        dataset.transform.a * dataset.transform.e
        - dataset.transform.b * dataset.transform.d
    )
    if determinant <= 0:
        raise ValueError("raster transform must define a positive pixel area")
    return determinant * unit_factor * unit_factor


class SpatialStatisticsService:
    """Calculate candidate and valid-observation area inside one boundary.

    Boundary inclusion uses pixel centres (`all_touched=False`). Candidate pixels
    outside the independent valid-observation mask never contribute to area.
    """

    def calculate(self, command: SpatialStatisticsCommand) -> AreaStatistic:
        candidate_path = Path(command.candidate_mask_path)
        valid_path = Path(command.valid_observation_mask_path)
        boundary_path = Path(command.boundary_path)
        for path, label in (
            (candidate_path, "candidate mask"),
            (valid_path, "valid-observation mask"),
            (boundary_path, "boundary"),
        ):
            if not path.is_file():
                raise FileNotFoundError(f"{label} does not exist: {path}")

        geometries, boundary_crs = _load_boundary(boundary_path)
        with rasterio.open(candidate_path) as candidate, rasterio.open(valid_path) as valid:
            if candidate.count != 1 or valid.count != 1:
                raise ValueError("candidate and valid-observation masks must be single-band")
            _require_aligned(candidate, valid)
            if candidate.crs is None:
                raise ValueError("candidate mask must declare a CRS")

            candidate_array = candidate.read(1)
            valid_array = valid.read(1)
            _require_binary(candidate_array, name="candidate mask")
            _require_binary(valid_array, name="valid-observation mask")

            raster_geometries = geometries
            if boundary_crs != candidate.crs:
                raster_geometries = [
                    transform_geom(boundary_crs, candidate.crs, geometry)
                    for geometry in geometries
                ]
            inside_boundary = geometry_mask(
                raster_geometries,
                out_shape=(candidate.height, candidate.width),
                transform=candidate.transform,
                all_touched=False,
                invert=True,
            )
            valid_pixels = inside_boundary & (valid_array == 1)
            if not valid_pixels.any():
                raise ValueError("boundary contains no valid observed pixels")
            candidate_pixels = valid_pixels & (candidate_array == 1)
            pixel_area_m2 = _pixel_area_square_metres(candidate)

        return AreaStatistic(
            statistic_id=command.statistic_id,
            management_unit=command.management_unit,
            remote_sensing_result=command.remote_sensing_result,
            candidate_area_m2=float(candidate_pixels.sum() * pixel_area_m2),
            valid_observation_area_m2=float(valid_pixels.sum() * pixel_area_m2),
            method="raster_mask_within_boundary",
            calculated_at=command.calculated_at,
            quality=command.quality,
            version=command.version,
        )
