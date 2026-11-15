"""Read-only SQLAlchemy implementation of the domain repository contract."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql.ranges import Range
from sqlalchemy.orm import Session

from oge_main.domain.models import (
    AreaStatistic,
    DateRange,
    IrrigationQuotaAssignment,
    IrrigationQuotaDefinition,
    ManagementUnit,
    RemoteSensingResult,
    SpatialAsset,
    VersionedReference,
    VersionInfo,
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


def _reference(record_id: str | None, revision: int | None) -> VersionedReference | None:
    if record_id is None and revision is None:
        return None
    if record_id is None or revision is None:
        raise ValueError("partial version reference stored in database")
    return VersionedReference(record_id=record_id, revision=revision)


def _date_range(value: Range[date]) -> DateRange:
    if value.empty or value.lower is None or value.upper is None:
        raise ValueError("database date range must be finite and non-empty")
    end_date = value.upper if value.upper_inc else value.upper - timedelta(days=1)
    start_date = value.lower if value.lower_inc else value.lower + timedelta(days=1)
    return DateRange(start_date=start_date, end_date=end_date)


def _version(
    *,
    revision: int,
    previous_id: str | None,
    previous_revision: int | None,
    status: str,
    change_reason: str,
    changed_by: str,
    changed_at,
    feedback_id: str | None,
) -> VersionInfo:
    return VersionInfo(
        revision=revision,
        previous=_reference(previous_id, previous_revision),
        status=status,
        change_reason=change_reason,
        changed_by=changed_by,
        changed_at=changed_at,
        feedback_id=feedback_id,
    )


class SqlAlchemyDomainRepository:
    """Map explicit immutable database versions to strict domain models."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _missing(kind: str, reference: VersionedReference) -> LookupError:
        return LookupError(
            f"{kind} version {(reference.record_id, reference.revision)!r} was not found"
        )

    def _asset(self, asset_id: str) -> SpatialAsset:
        row = self.session.get(SpatialAssetRow, asset_id)
        if row is None:
            raise LookupError(f"spatial asset {asset_id!r} was not found")
        return SpatialAsset(
            asset_id=row.asset_id,
            href=row.href,
            media_type=row.media_type,
            roles=row.roles,
            crs=row.crs,
            checksum_sha256=row.checksum_sha256,
            created_at=row.created_at,
            source=row.source,
        )

    def get_management_unit(self, reference: VersionedReference) -> ManagementUnit:
        row = self.session.get(ManagementUnitVersionRow, (reference.record_id, reference.revision))
        if row is None:
            raise self._missing("management unit", reference)
        return ManagementUnit(
            unit_id=row.unit_id,
            name=row.name,
            unit_type=row.unit_type,
            boundary=self._asset(row.boundary_asset_id),
            valid_period=_date_range(row.valid_period),
            root_district=VersionedReference(
                record_id=row.root_unit_id, revision=row.root_revision
            ),
            parent=_reference(row.parent_unit_id, row.parent_revision),
            quality=row.quality,
            version=_version(
                revision=row.revision,
                previous_id=row.previous_unit_id,
                previous_revision=row.previous_revision,
                status=row.status,
                change_reason=row.change_reason,
                changed_by=row.changed_by,
                changed_at=row.changed_at,
                feedback_id=row.feedback_id,
            ),
        )

    def get_remote_sensing_result(self, reference: VersionedReference) -> RemoteSensingResult:
        row = self.session.get(
            RemoteSensingResultVersionRow, (reference.record_id, reference.revision)
        )
        if row is None:
            raise self._missing("remote-sensing result", reference)
        unit_ids = self.session.scalars(
            select(RemoteResultManagementUnitRow.unit_id)
            .where(
                RemoteResultManagementUnitRow.result_id == row.result_id,
                RemoteResultManagementUnitRow.result_revision == row.revision,
            )
            .order_by(RemoteResultManagementUnitRow.unit_id)
        ).all()
        return RemoteSensingResult(
            result_id=row.result_id,
            target=row.target,
            management_unit_ids=list(unit_ids),
            observation_period=_date_range(row.observation_period),
            mask_asset=self._asset(row.mask_asset_id),
            model_name=row.model_name,
            model_version=row.model_version,
            produced_at=row.produced_at,
            quality=row.quality,
            version=_version(
                revision=row.revision,
                previous_id=row.previous_result_id,
                previous_revision=row.previous_revision,
                status=row.status,
                change_reason=row.change_reason,
                changed_by=row.changed_by,
                changed_at=row.changed_at,
                feedback_id=row.feedback_id,
            ),
        )

    def get_quota_definition(self, reference: VersionedReference) -> IrrigationQuotaDefinition:
        row = self.session.get(
            IrrigationQuotaDefinitionVersionRow,
            (reference.record_id, reference.revision),
        )
        if row is None:
            raise self._missing("quota definition", reference)
        return IrrigationQuotaDefinition(
            quota_id=row.quota_id,
            crop_code=row.crop_code,
            stage_code=row.stage_code,
            value_m3_per_mu=row.value_m3_per_mu,
            source=row.source,
            quality=row.quality,
            version=_version(
                revision=row.revision,
                previous_id=row.previous_quota_id,
                previous_revision=row.previous_revision,
                status=row.status,
                change_reason=row.change_reason,
                changed_by=row.changed_by,
                changed_at=row.changed_at,
                feedback_id=row.feedback_id,
            ),
        )

    def get_quota_assignment(self, reference: VersionedReference) -> IrrigationQuotaAssignment:
        row = self.session.get(
            IrrigationQuotaAssignmentVersionRow,
            (reference.record_id, reference.revision),
        )
        if row is None:
            raise self._missing("quota assignment", reference)
        return IrrigationQuotaAssignment(
            assignment_id=row.assignment_id,
            management_unit_id=row.management_unit_id,
            quota=VersionedReference(record_id=row.quota_id, revision=row.quota_revision),
            valid_period=_date_range(row.valid_period),
            version=_version(
                revision=row.revision,
                previous_id=row.previous_assignment_id,
                previous_revision=row.previous_revision,
                status=row.status,
                change_reason=row.change_reason,
                changed_by=row.changed_by,
                changed_at=row.changed_at,
                feedback_id=row.feedback_id,
            ),
        )

    def get_area_statistic(self, reference: VersionedReference) -> AreaStatistic:
        row = self.session.get(AreaStatisticVersionRow, (reference.record_id, reference.revision))
        if row is None:
            raise self._missing("area statistic", reference)
        return self._area_statistic(row)

    def find_area_statistic(
        self,
        management_unit: VersionedReference,
        remote_sensing_result: VersionedReference,
    ) -> AreaStatistic:
        statement = select(AreaStatisticVersionRow).where(
            AreaStatisticVersionRow.management_unit_id == management_unit.record_id,
            AreaStatisticVersionRow.management_unit_revision == management_unit.revision,
            AreaStatisticVersionRow.remote_result_id == remote_sensing_result.record_id,
            AreaStatisticVersionRow.remote_result_revision == remote_sensing_result.revision,
            AreaStatisticVersionRow.status == "active",
        )
        row = self.session.scalar(statement)
        if row is None:
            raise LookupError(
                "exactly one active area statistic is required for each management-unit "
                "and remote-sensing-result version"
            )
        return self._area_statistic(row)

    @staticmethod
    def _area_statistic(row: AreaStatisticVersionRow) -> AreaStatistic:
        return AreaStatistic(
            statistic_id=row.statistic_id,
            management_unit=VersionedReference(
                record_id=row.management_unit_id,
                revision=row.management_unit_revision,
            ),
            remote_sensing_result=VersionedReference(
                record_id=row.remote_result_id,
                revision=row.remote_result_revision,
            ),
            candidate_area_m2=row.candidate_area_m2,
            valid_observation_area_m2=row.valid_observation_area_m2,
            method=row.method,
            calculated_at=row.calculated_at,
            quality=row.quality,
            version=_version(
                revision=row.revision,
                previous_id=row.previous_statistic_id,
                previous_revision=row.previous_revision,
                status=row.status,
                change_reason=row.change_reason,
                changed_by=row.changed_by,
                changed_at=row.changed_at,
                feedback_id=row.feedback_id,
            ),
        )
