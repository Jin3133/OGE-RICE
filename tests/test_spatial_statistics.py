from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from oge_main.application import (
    AssessmentService,
    InMemoryDomainRepository,
    SpatialStatisticsCommand,
    SpatialStatisticsJob,
    SpatialStatisticsService,
)
from oge_main.domain import (
    AnalysisTask,
    IrrigationQuotaAssignment,
    IrrigationQuotaDefinition,
    ManagementUnit,
    RemoteSensingResult,
)
from oge_main.domain.models import DataQuality, VersionedReference, VersionInfo

EXAMPLES = Path("examples/domain/v1")


def write_raster(path: Path, values: np.ndarray, *, transform=None, crs="EPSG:32650") -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=values.shape[1],
        height=values.shape[0],
        count=1,
        dtype=values.dtype,
        crs=crs,
        transform=transform or from_origin(0, 40, 10, 10),
    ) as target:
        target.write(values, 1)


def write_boundary(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {
                    "type": "name",
                    "properties": {"name": "urn:ogc:def:crs:EPSG::32650"},
                },
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 20], [30, 20], [30, 40], [0, 40], [0, 20]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def command(tmp_path: Path) -> SpatialStatisticsCommand:
    return SpatialStatisticsCommand(
        statistic_id="area.example.v1",
        management_unit=VersionedReference(record_id="unit.example", revision=1),
        remote_sensing_result=VersionedReference(record_id="rs.example", revision=1),
        candidate_mask_path=tmp_path / "candidate.tif",
        valid_observation_mask_path=tmp_path / "valid.tif",
        boundary_path=tmp_path / "boundary.geojson",
        calculated_at=datetime.fromisoformat("2026-11-14T10:00:00+08:00"),
        quality=DataQuality(status="illustrative", statement="Synthetic spatial test."),
        version=VersionInfo(
            revision=1,
            status="active",
            change_reason="Initial synthetic statistic.",
            changed_by="test",
            changed_at=datetime.fromisoformat("2026-11-14T10:00:00+08:00"),
        ),
    )


def test_calculates_only_valid_candidate_pixels_inside_boundary(tmp_path: Path) -> None:
    candidate = np.array(
        [[1, 1, 0, 1], [1, 0, 1, 1], [1, 1, 1, 1], [0, 0, 0, 0]], dtype=np.uint8
    )
    valid = np.array(
        [[1, 1, 1, 1], [1, 0, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]], dtype=np.uint8
    )
    write_raster(tmp_path / "candidate.tif", candidate)
    write_raster(tmp_path / "valid.tif", valid)
    write_boundary(tmp_path / "boundary.geojson")

    result = SpatialStatisticsService().calculate(command(tmp_path))

    assert result.valid_observation_area_m2 == 500
    assert result.candidate_area_m2 == 400
    assert result.management_unit.record_id == "unit.example"


def test_rejects_unaligned_masks(tmp_path: Path) -> None:
    values = np.ones((4, 4), dtype=np.uint8)
    write_raster(tmp_path / "candidate.tif", values)
    write_raster(
        tmp_path / "valid.tif", values, transform=from_origin(5, 40, 10, 10)
    )
    write_boundary(tmp_path / "boundary.geojson")

    with pytest.raises(ValueError, match="same transform"):
        SpatialStatisticsService().calculate(command(tmp_path))


def test_rejects_non_binary_mask(tmp_path: Path) -> None:
    candidate = np.ones((4, 4), dtype=np.uint8)
    candidate[0, 0] = 2
    write_raster(tmp_path / "candidate.tif", candidate)
    write_raster(tmp_path / "valid.tif", np.ones((4, 4), dtype=np.uint8))
    write_boundary(tmp_path / "boundary.geojson")

    with pytest.raises(ValueError, match="candidate mask must be binary"):
        SpatialStatisticsService().calculate(command(tmp_path))


def test_rejects_boundary_without_valid_observations(tmp_path: Path) -> None:
    write_raster(tmp_path / "candidate.tif", np.ones((4, 4), dtype=np.uint8))
    write_raster(tmp_path / "valid.tif", np.zeros((4, 4), dtype=np.uint8))
    write_boundary(tmp_path / "boundary.geojson")

    with pytest.raises(ValueError, match="no valid observed pixels"):
        SpatialStatisticsService().calculate(command(tmp_path))


def test_job_resolves_relative_paths_from_its_own_directory(tmp_path: Path) -> None:
    job = SpatialStatisticsJob(
        statistic_id="area.example.v1",
        management_unit={"record_id": "unit.example", "revision": 1},
        remote_sensing_result={"record_id": "rs.example", "revision": 1},
        candidate_mask_path="rasters/candidate.tif",
        valid_observation_mask_path="rasters/valid.tif",
        boundary_path="boundaries/unit.geojson",
        calculated_at="2026-11-14T10:00:00+08:00",
        quality={"status": "illustrative", "statement": "Path test."},
        version={
            "revision": 1,
            "previous": None,
            "status": "active",
            "change_reason": "Path test.",
            "changed_by": "test",
            "changed_at": "2026-11-14T10:00:00+08:00",
            "feedback_id": None,
        },
    )

    resolved = job.to_command(base_directory=tmp_path)

    assert resolved.candidate_mask_path == tmp_path / "rasters/candidate.tif"
    assert resolved.boundary_path == tmp_path / "boundaries/unit.geojson"


def load_example(filename: str, model: type):
    return model.model_validate_json((EXAMPLES / filename).read_text(encoding="utf-8"))


def test_generated_area_statistic_feeds_formal_assessment(tmp_path: Path) -> None:
    candidate = np.array(
        [[1, 1, 0, 1], [1, 0, 1, 1], [1, 1, 1, 1], [0, 0, 0, 0]], dtype=np.uint8
    )
    valid = np.array(
        [[1, 1, 1, 1], [1, 0, 1, 1], [1, 1, 1, 1], [1, 1, 1, 1]], dtype=np.uint8
    )
    write_raster(tmp_path / "candidate.tif", candidate)
    write_raster(tmp_path / "valid.tif", valid)
    write_boundary(tmp_path / "boundary.geojson")
    spatial_command = command(tmp_path)
    spatial_command = SpatialStatisticsCommand(
        statistic_id=spatial_command.statistic_id,
        management_unit=VersionedReference(record_id="jx.zone.01", revision=1),
        remote_sensing_result=VersionedReference(
            record_id="rs.jx.2025.tillering.v1", revision=1
        ),
        candidate_mask_path=spatial_command.candidate_mask_path,
        valid_observation_mask_path=spatial_command.valid_observation_mask_path,
        boundary_path=spatial_command.boundary_path,
        calculated_at=spatial_command.calculated_at,
        quality=spatial_command.quality,
        version=spatial_command.version,
    )
    area_statistic = SpatialStatisticsService().calculate(spatial_command)
    repository = InMemoryDomainRepository(
        management_units=[
            load_example("irrigation-district.json", ManagementUnit),
            load_example("management-unit.json", ManagementUnit),
        ],
        remote_sensing_results=[
            load_example("remote-sensing-result.json", RemoteSensingResult)
        ],
        quota_definitions=[
            load_example("irrigation-quota-definition.json", IrrigationQuotaDefinition)
        ],
        quota_assignments=[
            load_example("irrigation-quota-assignment.json", IrrigationQuotaAssignment)
        ],
        area_statistics=[area_statistic],
    )

    assessment = AssessmentService(repository).calculate(
        load_example("analysis-task.json", AnalysisTask),
        assessment_id="assessment.spatial-integration",
        generated_at=datetime.fromisoformat("2026-11-14T10:30:00+08:00"),
    )

    assert assessment.total_candidate_area_m2 == 400
    assert assessment.total_reference_irrigation_demand_m3 == pytest.approx(48)
