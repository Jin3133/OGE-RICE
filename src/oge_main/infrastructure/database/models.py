"""Infrastructure tables shared by versioned business aggregates."""

from __future__ import annotations

from datetime import date, datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, DATERANGE, JSONB, ExcludeConstraint
from sqlalchemy.dialects.postgresql.ranges import Range
from sqlalchemy.orm import Mapped, mapped_column

from oge_main.infrastructure.database.base import Base


class ResourceHeadRow(Base):
    __tablename__ = "resource_heads"

    resource_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (CheckConstraint("current_revision >= 1", name="current_revision_positive"),)


class OperationRow(Base):
    __tablename__ = "operations"

    operation_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    submitted_by: Mapped[str] = mapped_column(String(100), nullable=False)
    target_resource_type: Mapped[str | None] = mapped_column(String(50))
    target_resource_id: Mapped[str | None] = mapped_column(String(100))
    target_revision: Mapped[int | None] = mapped_column(Integer)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="status_allowed",
        ),
        CheckConstraint(
            "target_revision IS NULL OR target_revision >= 1",
            name="target_revision_positive",
        ),
    )


class OperationAttemptRow(Base):
    __tablename__ = "operation_attempts"

    operation_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    attempt_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    worker_id: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    log_reference: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        ForeignKeyConstraint(
            ["operation_id"],
            ["operations.operation_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="status_allowed",
        ),
    )


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    request_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_revision: Mapped[int | None] = mapped_column(Integer)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint(
            "resource_revision IS NULL OR resource_revision >= 1",
            name="resource_revision_positive",
        ),
    )


class IdempotencyRecordRow(Base):
    __tablename__ = "idempotency_records"

    actor_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    resource_revision: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'completed', 'failed')",
            name="status_allowed",
        ),
        CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'",
            name="request_hash_sha256",
        ),
        CheckConstraint(
            "resource_revision IS NULL OR resource_revision >= 1",
            name="resource_revision_positive",
        ),
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
    )


class SpatialAssetRow(Base):
    __tablename__ = "spatial_assets"

    asset_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    href: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    roles: Mapped[list[str]] = mapped_column(ARRAY(String(30)), nullable=False)
    crs: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[dict] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        CheckConstraint("cardinality(roles) > 0", name="roles_not_empty"),
        CheckConstraint(
            "checksum_sha256 IS NULL OR checksum_sha256 ~ '^[0-9a-f]{64}$'",
            name="checksum_sha256_valid",
        ),
    )


class ReferenceAreaVersionRow(Base):
    __tablename__ = "reference_area_versions"

    area_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    area_type: Mapped[str] = mapped_column(String(40), nullable=False)
    administrative_code: Mapped[str | None] = mapped_column(String(20))
    boundary_asset_id: Mapped[str] = mapped_column(
        ForeignKey("spatial_assets.asset_id", ondelete="RESTRICT"), nullable=False
    )
    geom: Mapped[object] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False
    )
    quality: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_area_id: Mapped[str | None] = mapped_column(String(100))
    previous_revision: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["previous_area_id", "previous_revision"],
            ["reference_area_versions.area_id", "reference_area_versions.revision"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint(
            "area_type IN ('administrative_district', 'technical_study_area')",
            name="area_type_allowed",
        ),
        CheckConstraint("ST_SRID(geom) = 4326", name="geom_srid_4326"),
        CheckConstraint("NOT ST_IsEmpty(geom)", name="geom_not_empty"),
        CheckConstraint("ST_IsValid(geom)", name="geom_valid"),
        CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'withdrawn')",
            name="status_allowed",
        ),
        CheckConstraint(
            "(revision = 1 AND previous_area_id IS NULL AND previous_revision IS NULL) OR "
            "(revision > 1 AND previous_area_id = area_id AND previous_revision < revision)",
            name="previous_version_consistent",
        ),
        Index("ix_reference_area_versions_geom", "geom", postgresql_using="gist"),
    )


class ManagementUnitVersionRow(Base):
    __tablename__ = "management_unit_versions"

    unit_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    unit_type: Mapped[str] = mapped_column(String(30), nullable=False)
    boundary_asset_id: Mapped[str] = mapped_column(
        ForeignKey("spatial_assets.asset_id", ondelete="RESTRICT"), nullable=False
    )
    valid_period: Mapped[Range[date]] = mapped_column(DATERANGE, nullable=False)
    root_unit_id: Mapped[str] = mapped_column(String(100), nullable=False)
    root_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_unit_id: Mapped[str | None] = mapped_column(String(100))
    parent_revision: Mapped[int | None] = mapped_column(Integer)
    geom: Mapped[object] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False
    )
    quality: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_unit_id: Mapped[str | None] = mapped_column(String(100))
    previous_revision: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feedback_id: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        ForeignKeyConstraint(
            ["root_unit_id", "root_revision"],
            ["management_unit_versions.unit_id", "management_unit_versions.revision"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["parent_unit_id", "parent_revision"],
            ["management_unit_versions.unit_id", "management_unit_versions.revision"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["previous_unit_id", "previous_revision"],
            ["management_unit_versions.unit_id", "management_unit_versions.revision"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint(
            "unit_type IN ('irrigation_district', 'management_zone', 'custom')",
            name="unit_type_allowed",
        ),
        CheckConstraint("NOT isempty(valid_period)", name="valid_period_not_empty"),
        CheckConstraint("ST_SRID(geom) = 4326", name="geom_srid_4326"),
        CheckConstraint("NOT ST_IsEmpty(geom)", name="geom_not_empty"),
        CheckConstraint("ST_IsValid(geom)", name="geom_valid"),
        CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'withdrawn')",
            name="status_allowed",
        ),
        CheckConstraint(
            "(revision = 1 AND previous_unit_id IS NULL AND previous_revision IS NULL) OR "
            "(revision > 1 AND previous_unit_id = unit_id AND previous_revision < revision)",
            name="previous_version_consistent",
        ),
        CheckConstraint(
            "(unit_type = 'irrigation_district' AND parent_unit_id IS NULL "
            "AND parent_revision IS NULL AND root_unit_id = unit_id "
            "AND root_revision = revision) OR "
            "(unit_type <> 'irrigation_district' AND parent_unit_id IS NOT NULL "
            "AND parent_revision IS NOT NULL)",
            name="root_and_parent_shape",
        ),
        Index("ix_management_unit_versions_geom", "geom", postgresql_using="gist"),
    )


class RemoteSensingResultVersionRow(Base):
    __tablename__ = "remote_sensing_result_versions"

    result_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    target: Mapped[str] = mapped_column(String(50), nullable=False)
    observation_period: Mapped[Range[date]] = mapped_column(DATERANGE, nullable=False)
    mask_asset_id: Mapped[str] = mapped_column(
        ForeignKey("spatial_assets.asset_id", ondelete="RESTRICT"), nullable=False
    )
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    produced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quality: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_result_id: Mapped[str | None] = mapped_column(String(100))
    previous_revision: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feedback_id: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        ForeignKeyConstraint(
            ["previous_result_id", "previous_revision"],
            [
                "remote_sensing_result_versions.result_id",
                "remote_sensing_result_versions.revision",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint("target = 'cultivated_land_candidate'", name="target_supported"),
        CheckConstraint("NOT isempty(observation_period)", name="observation_period_not_empty"),
        CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'withdrawn')",
            name="status_allowed",
        ),
        CheckConstraint(
            "(revision = 1 AND previous_result_id IS NULL AND previous_revision IS NULL) OR "
            "(revision > 1 AND previous_result_id = result_id AND previous_revision < revision)",
            name="previous_version_consistent",
        ),
    )


class RemoteResultManagementUnitRow(Base):
    __tablename__ = "remote_result_management_units"

    result_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    result_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(100), primary_key=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["result_id", "result_revision"],
            [
                "remote_sensing_result_versions.result_id",
                "remote_sensing_result_versions.revision",
            ],
            ondelete="CASCADE",
        ),
    )


class IrrigationQuotaDefinitionVersionRow(Base):
    __tablename__ = "irrigation_quota_definition_versions"

    quota_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    crop_code: Mapped[str] = mapped_column(String(30), nullable=False)
    stage_code: Mapped[str] = mapped_column(String(100), nullable=False)
    value_m3_per_mu: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[dict] = mapped_column(JSONB, nullable=False)
    quality: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_quota_id: Mapped[str | None] = mapped_column(String(100))
    previous_revision: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feedback_id: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        ForeignKeyConstraint(
            ["previous_quota_id", "previous_revision"],
            [
                "irrigation_quota_definition_versions.quota_id",
                "irrigation_quota_definition_versions.revision",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint("crop_code = 'rice'", name="crop_supported"),
        CheckConstraint("value_m3_per_mu > 0", name="value_positive"),
        CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'withdrawn')",
            name="status_allowed",
        ),
        CheckConstraint(
            "(revision = 1 AND previous_quota_id IS NULL AND previous_revision IS NULL) OR "
            "(revision > 1 AND previous_quota_id = quota_id AND previous_revision < revision)",
            name="previous_version_consistent",
        ),
    )


class IrrigationQuotaAssignmentVersionRow(Base):
    __tablename__ = "irrigation_quota_assignment_versions"

    assignment_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    management_unit_id: Mapped[str] = mapped_column(String(100), nullable=False)
    quota_id: Mapped[str] = mapped_column(String(100), nullable=False)
    quota_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    crop_code: Mapped[str] = mapped_column(String(30), nullable=False)
    stage_code: Mapped[str] = mapped_column(String(100), nullable=False)
    valid_period: Mapped[Range[date]] = mapped_column(DATERANGE, nullable=False)
    previous_assignment_id: Mapped[str | None] = mapped_column(String(100))
    previous_revision: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feedback_id: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        ForeignKeyConstraint(
            ["quota_id", "quota_revision"],
            [
                "irrigation_quota_definition_versions.quota_id",
                "irrigation_quota_definition_versions.revision",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["previous_assignment_id", "previous_revision"],
            [
                "irrigation_quota_assignment_versions.assignment_id",
                "irrigation_quota_assignment_versions.revision",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint("crop_code = 'rice'", name="crop_supported"),
        CheckConstraint("NOT isempty(valid_period)", name="valid_period_not_empty"),
        CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'withdrawn')",
            name="status_allowed",
        ),
        CheckConstraint(
            "(revision = 1 AND previous_assignment_id IS NULL AND previous_revision IS NULL) OR "
            "(revision > 1 AND previous_assignment_id = assignment_id "
            "AND previous_revision < revision)",
            name="previous_version_consistent",
        ),
        ExcludeConstraint(
            ("management_unit_id", "="),
            ("crop_code", "="),
            ("stage_code", "="),
            ("valid_period", "&&"),
            where=text("status = 'active'"),
            using="gist",
            name="excl_quota_assignment_active_period",
        ),
    )


class AreaStatisticVersionRow(Base):
    __tablename__ = "area_statistic_versions"

    statistic_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    management_unit_id: Mapped[str] = mapped_column(String(100), nullable=False)
    management_unit_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    remote_result_id: Mapped[str] = mapped_column(String(100), nullable=False)
    remote_result_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_area_m2: Mapped[float] = mapped_column(Float, nullable=False)
    valid_observation_area_m2: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quality: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_statistic_id: Mapped[str | None] = mapped_column(String(100))
    previous_revision: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    feedback_id: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        ForeignKeyConstraint(
            ["management_unit_id", "management_unit_revision"],
            ["management_unit_versions.unit_id", "management_unit_versions.revision"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["remote_result_id", "remote_result_revision"],
            [
                "remote_sensing_result_versions.result_id",
                "remote_sensing_result_versions.revision",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["previous_statistic_id", "previous_revision"],
            ["area_statistic_versions.statistic_id", "area_statistic_versions.revision"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint("candidate_area_m2 >= 0", name="candidate_area_nonnegative"),
        CheckConstraint("valid_observation_area_m2 > 0", name="valid_observation_area_positive"),
        CheckConstraint(
            "candidate_area_m2 <= valid_observation_area_m2",
            name="candidate_within_valid_observation",
        ),
        CheckConstraint("method = 'raster_mask_within_boundary'", name="method_supported"),
        CheckConstraint(
            "status IN ('draft', 'active', 'superseded', 'withdrawn')",
            name="status_allowed",
        ),
        CheckConstraint(
            "(revision = 1 AND previous_statistic_id IS NULL AND previous_revision IS NULL) OR "
            "(revision > 1 AND previous_statistic_id = statistic_id "
            "AND previous_revision < revision)",
            name="previous_version_consistent",
        ),
        Index(
            "uq_area_statistic_active_input",
            "management_unit_id",
            "management_unit_revision",
            "remote_result_id",
            "remote_result_revision",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )
