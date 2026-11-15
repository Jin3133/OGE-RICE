from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql.ranges import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from oge_main.application.assessment import AssessmentService
from oge_main.domain.models import (
    AnalysisTask,
    AreaStatistic,
    IrrigationQuotaAssignment,
    IrrigationQuotaDefinition,
    ManagementUnit,
    RemoteSensingResult,
    SpatialAsset,
    VersionedReference,
)
from oge_main.infrastructure.database.models import (
    AreaStatisticVersionRow,
    IrrigationQuotaAssignmentVersionRow,
    IrrigationQuotaDefinitionVersionRow,
    ManagementUnitVersionRow,
    RemoteResultManagementUnitRow,
    RemoteSensingResultVersionRow,
    SpatialAssetRow,
)
from oge_main.infrastructure.database.repository import SqlAlchemyDomainRepository

DATABASE_URL = os.getenv("OGE_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="OGE_TEST_DATABASE_URL is required for PostGIS integration tests",
)
EXAMPLES = Path("examples/domain/v1")


def load(filename: str, model: type):
    return model.model_validate_json((EXAMPLES / filename).read_text(encoding="utf-8"))


@pytest.fixture
def session():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    connection = engine.connect()
    transaction = connection.begin()
    database_session = Session(bind=connection, expire_on_commit=False)
    try:
        yield database_session
    finally:
        database_session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def date_range(value) -> Range:
    return Range(value.start_date, value.end_date, bounds="[]")


def version_values(record) -> dict:
    previous = record.version.previous
    return {
        "revision": record.version.revision,
        "previous_revision": previous.revision if previous else None,
        "status": record.version.status.value,
        "change_reason": record.version.change_reason,
        "changed_by": record.version.changed_by,
        "changed_at": record.version.changed_at,
        "feedback_id": record.version.feedback_id,
    }


def add_asset(session: Session, asset: SpatialAsset) -> None:
    session.add(
        SpatialAssetRow(
            asset_id=asset.asset_id,
            href=asset.href,
            media_type=asset.media_type.value,
            roles=[role.value for role in asset.roles],
            crs=asset.crs,
            checksum_sha256=asset.checksum_sha256,
            created_at=asset.created_at,
            source=asset.source.model_dump(mode="json"),
        )
    )


def add_management_unit(session: Session, unit: ManagementUnit, geometry_wkt: str) -> None:
    previous = unit.version.previous
    session.add(
        ManagementUnitVersionRow(
            unit_id=unit.unit_id,
            name=unit.name,
            unit_type=unit.unit_type,
            boundary_asset_id=unit.boundary.asset_id,
            valid_period=date_range(unit.valid_period),
            root_unit_id=unit.root_district.record_id,
            root_revision=unit.root_district.revision,
            parent_unit_id=unit.parent.record_id if unit.parent else None,
            parent_revision=unit.parent.revision if unit.parent else None,
            geom=WKTElement(geometry_wkt, srid=4326),
            quality=unit.quality.model_dump(mode="json"),
            previous_unit_id=previous.record_id if previous else None,
            **version_values(unit),
        )
    )


def seed_business_cycle(session: Session) -> None:
    district = load("irrigation-district.json", ManagementUnit)
    unit = load("management-unit.json", ManagementUnit)
    remote = load("remote-sensing-result.json", RemoteSensingResult)
    definition = load("irrigation-quota-definition.json", IrrigationQuotaDefinition)
    assignment = load("irrigation-quota-assignment.json", IrrigationQuotaAssignment)
    area = load("area-statistic.json", AreaStatistic)

    for asset in (district.boundary, unit.boundary, remote.mask_asset):
        add_asset(session, asset)
    session.flush()

    add_management_unit(
        session,
        district,
        "MULTIPOLYGON(((114.20 30.20,114.50 30.20,114.50 30.50,114.20 30.50,114.20 30.20)))",
    )
    session.flush()
    add_management_unit(
        session,
        unit,
        "MULTIPOLYGON(((114.25 30.25,114.35 30.25,114.35 30.35,114.25 30.35,114.25 30.25)))",
    )
    session.flush()

    remote_previous = remote.version.previous
    session.add(
        RemoteSensingResultVersionRow(
            result_id=remote.result_id,
            target=remote.target,
            observation_period=date_range(remote.observation_period),
            mask_asset_id=remote.mask_asset.asset_id,
            model_name=remote.model_name,
            model_version=remote.model_version,
            produced_at=remote.produced_at,
            quality=remote.quality.model_dump(mode="json"),
            previous_result_id=remote_previous.record_id if remote_previous else None,
            **version_values(remote),
        )
    )
    session.flush()
    session.add_all(
        RemoteResultManagementUnitRow(
            result_id=remote.result_id,
            result_revision=remote.version.revision,
            unit_id=unit_id,
        )
        for unit_id in remote.management_unit_ids
    )

    definition_previous = definition.version.previous
    session.add(
        IrrigationQuotaDefinitionVersionRow(
            quota_id=definition.quota_id,
            crop_code=definition.crop_code,
            stage_code=definition.stage_code,
            value_m3_per_mu=definition.value_m3_per_mu,
            source=definition.source.model_dump(mode="json"),
            quality=definition.quality.model_dump(mode="json"),
            previous_quota_id=(definition_previous.record_id if definition_previous else None),
            **version_values(definition),
        )
    )
    session.flush()

    assignment_previous = assignment.version.previous
    session.add(
        IrrigationQuotaAssignmentVersionRow(
            assignment_id=assignment.assignment_id,
            management_unit_id=assignment.management_unit_id,
            quota_id=assignment.quota.record_id,
            quota_revision=assignment.quota.revision,
            crop_code=definition.crop_code,
            stage_code=definition.stage_code,
            valid_period=date_range(assignment.valid_period),
            previous_assignment_id=(assignment_previous.record_id if assignment_previous else None),
            **version_values(assignment),
        )
    )
    session.flush()

    area_previous = area.version.previous
    session.add(
        AreaStatisticVersionRow(
            statistic_id=area.statistic_id,
            management_unit_id=area.management_unit.record_id,
            management_unit_revision=area.management_unit.revision,
            remote_result_id=area.remote_sensing_result.record_id,
            remote_result_revision=area.remote_sensing_result.revision,
            candidate_area_m2=area.candidate_area_m2,
            valid_observation_area_m2=area.valid_observation_area_m2,
            method=area.method,
            calculated_at=area.calculated_at,
            quality=area.quality.model_dump(mode="json"),
            previous_statistic_id=area_previous.record_id if area_previous else None,
            **version_values(area),
        )
    )
    session.flush()


def test_database_repository_drives_reference_demand_assessment(session: Session) -> None:
    seed_business_cycle(session)
    repository = SqlAlchemyDomainRepository(session)
    task = load("analysis-task.json", AnalysisTask)

    result = AssessmentService(repository).calculate(
        task,
        assessment_id="assessment.database.integration",
        generated_at=datetime.fromisoformat("2026-11-16T09:00:00+08:00"),
    )

    assert result.total_candidate_area_m2 == 8_175_000
    assert result.total_candidate_area_mu == pytest.approx(12_262.5)
    assert result.total_reference_irrigation_demand_m3 == pytest.approx(981_000)
    snapshot = result.unit_results[0].input_snapshot
    assert snapshot.management_unit == VersionedReference(record_id="jx.zone.01", revision=1)
    assert snapshot.quota_m3_per_mu == 80


def test_database_rejects_overlapping_active_quota_assignments(session: Session) -> None:
    seed_business_cycle(session)
    original = load("irrigation-quota-assignment.json", IrrigationQuotaAssignment)

    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            IrrigationQuotaAssignmentVersionRow(
                assignment_id="quota-assignment.jx.zone.01.overlap",
                revision=1,
                management_unit_id=original.management_unit_id,
                quota_id=original.quota.record_id,
                quota_revision=original.quota.revision,
                crop_code="rice",
                stage_code="tillering",
                valid_period=Range(
                    original.valid_period.start_date,
                    original.valid_period.end_date,
                    bounds="[]",
                ),
                previous_assignment_id=None,
                previous_revision=None,
                status="active",
                change_reason="验证数据库重叠约束",
                changed_by="integration.test",
                changed_at=original.version.changed_at,
                feedback_id=None,
            )
        )
        session.flush()
