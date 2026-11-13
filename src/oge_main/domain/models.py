"""Strict domain contracts for the irrigation-demand application."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    model_validator,
)

Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class StrictModel(BaseModel):
    """Reject unmodelled fields so interface drift is visible immediately."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DataQualityStatus(str, Enum):
    ILLUSTRATIVE = "illustrative"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class AssetRole(str, Enum):
    DATA = "data"
    BOUNDARY = "boundary"
    MASK = "mask"
    METADATA = "metadata"
    OVERVIEW = "overview"


class MediaType(str, Enum):
    GEOTIFF = "image/tiff; application=geotiff"
    COG = "image/tiff; application=geotiff; profile=cloud-optimized"
    GEOJSON = "application/geo+json"
    GEOPACKAGE = "application/geopackage+sqlite3"
    JSON = "application/json"


class TaskStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RecordStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class StageSelectionMethod(str, Enum):
    AUTOMATIC = "automatic"
    USER_CONFIRMED = "user_confirmed"
    USER_MODIFIED = "user_modified"


class SourceReference(StrictModel):
    title: NonEmptyText
    publisher: NonEmptyText | None = None
    url: HttpUrl | None = None
    publication_year: int | None = Field(default=None, ge=1900, le=2100)
    retrieved_at: date | None = None


class DataQuality(StrictModel):
    status: DataQualityStatus
    statement: NonEmptyText
    reviewed_by: NonEmptyText | None = None
    reviewed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def require_review_evidence_when_verified(self) -> Self:
        if self.status is DataQualityStatus.VERIFIED and not (
            self.reviewed_by and self.reviewed_at
        ):
            raise ValueError("verified data requires reviewed_by and reviewed_at")
        return self


class DateRange(StrictModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self

    def overlaps(self, other: DateRange) -> bool:
        return self.start_date <= other.end_date and other.start_date <= self.end_date


class VersionedReference(StrictModel):
    record_id: Identifier
    revision: int = Field(ge=1)


class VersionInfo(StrictModel):
    revision: int = Field(ge=1)
    previous: VersionedReference | None = None
    status: RecordStatus
    change_reason: NonEmptyText
    changed_by: NonEmptyText
    changed_at: AwareDatetime
    feedback_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_version_chain(self) -> Self:
        if self.revision == 1 and self.previous is not None:
            raise ValueError("revision 1 must not reference a previous version")
        if self.revision > 1 and self.previous is None:
            raise ValueError("revision greater than 1 requires a previous version")
        if self.previous and self.previous.revision >= self.revision:
            raise ValueError("previous revision must be lower than the current revision")
        return self


class SpatialAsset(StrictModel):
    asset_id: Identifier
    href: NonEmptyText
    media_type: MediaType
    roles: list[AssetRole] = Field(min_length=1)
    crs: NonEmptyText
    checksum_sha256: Annotated[
        str, StringConstraints(pattern=r"^[0-9a-f]{64}$")
    ] | None = None
    created_at: AwareDatetime
    source: SourceReference


class ManagementUnit(StrictModel):
    unit_id: Identifier
    name: NonEmptyText
    unit_type: Literal["irrigation_district", "management_zone", "custom"]
    boundary: SpatialAsset
    valid_period: DateRange
    root_district: VersionedReference
    parent: VersionedReference | None = None
    quality: DataQuality
    version: VersionInfo

    @model_validator(mode="after")
    def validate_roles_and_local_hierarchy(self) -> Self:
        if AssetRole.BOUNDARY not in self.boundary.roles:
            raise ValueError("management unit boundary asset requires the boundary role")
        if self.unit_type == "irrigation_district":
            if self.parent is not None:
                raise ValueError("irrigation district must be a root without a parent")
            if self.root_district != VersionedReference(
                record_id=self.unit_id, revision=self.version.revision
            ):
                raise ValueError("irrigation district root reference must point to itself")
        elif self.parent is None:
            raise ValueError("non-root management unit requires a parent reference")
        if self.parent and self.parent.record_id == self.unit_id:
            raise ValueError("management unit cannot be its own parent")
        if self.version.previous and self.version.previous.record_id != self.unit_id:
            raise ValueError("previous management unit version must use the same unit_id")
        return self


class GrowthStageSelection(StrictModel):
    stage_code: Identifier
    stage_name: NonEmptyText
    method: StageSelectionMethod
    crop_calendar_id: Identifier
    effective_period: DateRange
    confirmed_by: NonEmptyText | None = None
    confirmed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def require_confirmation_for_manual_selection(self) -> Self:
        if self.method is not StageSelectionMethod.AUTOMATIC and not (
            self.confirmed_by and self.confirmed_at
        ):
            raise ValueError(
                "user-confirmed or modified stages require confirmed_by and confirmed_at"
            )
        return self


class IrrigationQuotaDefinition(StrictModel):
    quota_id: Identifier
    crop_code: Literal["rice"]
    stage_code: Identifier
    value_m3_per_mu: float = Field(gt=0)
    source: SourceReference
    quality: DataQuality
    version: VersionInfo

    @model_validator(mode="after")
    def validate_previous_identity(self) -> Self:
        if self.version.previous and self.version.previous.record_id != self.quota_id:
            raise ValueError("previous quota version must use the same quota_id")
        return self


class IrrigationQuotaAssignment(StrictModel):
    assignment_id: Identifier
    management_unit_id: Identifier
    quota: VersionedReference
    valid_period: DateRange
    version: VersionInfo

    @model_validator(mode="after")
    def validate_previous_identity(self) -> Self:
        if (
            self.version.previous
            and self.version.previous.record_id != self.assignment_id
        ):
            raise ValueError(
                "previous quota-assignment version must use the same assignment_id"
            )
        return self


class RemoteSensingResult(StrictModel):
    result_id: Identifier
    target: Literal["cultivated_land_candidate"]
    management_unit_ids: list[Identifier] = Field(min_length=1)
    observation_period: DateRange
    mask_asset: SpatialAsset
    model_name: NonEmptyText
    model_version: NonEmptyText
    produced_at: AwareDatetime
    quality: DataQuality
    version: VersionInfo

    @model_validator(mode="after")
    def require_mask_role(self) -> Self:
        if AssetRole.MASK not in self.mask_asset.roles:
            raise ValueError("remote-sensing mask asset requires the mask role")
        if self.version.previous and self.version.previous.record_id != self.result_id:
            raise ValueError("previous remote-sensing version must use the same result_id")
        return self


class AnalysisTaskCreate(StrictModel):
    name: NonEmptyText
    business_scope: NonEmptyText
    crop_code: Literal["rice"]
    analysis_period: DateRange
    growth_stage: GrowthStageSelection
    management_units: list[VersionedReference] = Field(min_length=1)
    remote_sensing_result: VersionedReference
    irrigation_quota_assignments: list[VersionedReference] = Field(min_length=1)
    created_by: NonEmptyText

    @model_validator(mode="after")
    def validate_unique_units_and_stage_period(self) -> Self:
        unit_keys = {(item.record_id, item.revision) for item in self.management_units}
        if len(self.management_units) != len(unit_keys):
            raise ValueError("management unit references must not contain duplicates")
        assignment_keys = {
            (item.record_id, item.revision)
            for item in self.irrigation_quota_assignments
        }
        if len(self.irrigation_quota_assignments) != len(assignment_keys):
            raise ValueError("quota assignment references must not contain duplicates")
        stage_period = self.growth_stage.effective_period
        if (
            stage_period.start_date > self.analysis_period.end_date
            or stage_period.end_date < self.analysis_period.start_date
        ):
            raise ValueError("growth stage period must overlap the analysis period")
        return self


class AnalysisTask(AnalysisTaskCreate):
    task_id: Identifier
    revision: int = Field(ge=1)
    previous: VersionedReference | None = None
    status: TaskStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime
    updated_by: NonEmptyText
    change_reason: NonEmptyText

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        if self.created_at > self.updated_at:
            raise ValueError("created_at must be on or before updated_at")
        if self.revision == 1 and self.previous is not None:
            raise ValueError("task revision 1 must not reference a previous version")
        if self.revision > 1 and self.previous is None:
            raise ValueError("task revision greater than 1 requires a previous version")
        if self.previous:
            if self.previous.record_id != self.task_id:
                raise ValueError("previous task version must use the same task_id")
            if self.previous.revision >= self.revision:
                raise ValueError("previous task revision must be lower than current revision")
        return self


class FeedbackRecord(StrictModel):
    feedback_id: Identifier
    task_id: Identifier
    base_revision: int = Field(ge=1)
    target_type: Literal[
        "management_unit_boundary",
        "candidate_mask",
        "growth_stage",
        "irrigation_quota",
    ]
    target_id: Identifier
    field_name: Identifier
    previous_value: Any
    proposed_value: Any
    reason: NonEmptyText
    submitted_by: NonEmptyText
    submitted_at: AwareDatetime


class AreaStatistic(StrictModel):
    statistic_id: Identifier
    management_unit: VersionedReference
    remote_sensing_result: VersionedReference
    candidate_area_m2: float = Field(ge=0)
    valid_observation_area_m2: float = Field(gt=0)
    method: Literal["raster_mask_within_boundary"]
    calculated_at: AwareDatetime
    quality: DataQuality
    version: VersionInfo

    @model_validator(mode="after")
    def validate_area_and_previous_identity(self) -> Self:
        if self.candidate_area_m2 > self.valid_observation_area_m2:
            raise ValueError("candidate area cannot exceed valid observation area")
        if self.version.previous and self.version.previous.record_id != self.statistic_id:
            raise ValueError("previous area-statistic version must use the same statistic_id")
        return self


class DemandInputSnapshot(StrictModel):
    management_unit: VersionedReference
    remote_sensing_result: VersionedReference
    area_statistic: VersionedReference
    quota_assignment: VersionedReference
    quota_definition: VersionedReference
    stage_code: Identifier
    candidate_area_m2: float = Field(ge=0)
    candidate_area_mu: float = Field(ge=0)
    quota_m3_per_mu: float = Field(gt=0)


class UnitDemandResult(StrictModel):
    unit_id: Identifier
    input_snapshot: DemandInputSnapshot
    reference_irrigation_demand_m3: float = Field(ge=0)


class ReferenceDemandAssessment(StrictModel):
    assessment_id: Identifier
    task: VersionedReference
    generated_at: AwareDatetime
    formula: Literal["W_m3 = A_mu * M_m3_per_mu"]
    unit_results: list[UnitDemandResult] = Field(min_length=1)
    total_candidate_area_m2: float = Field(ge=0)
    total_candidate_area_mu: float = Field(ge=0)
    total_reference_irrigation_demand_m3: float = Field(ge=0)
    limitations: list[NonEmptyText] = Field(min_length=1)
