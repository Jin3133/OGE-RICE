"""Stable HTTP-only contracts that do not belong to the business domain."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorDetail(ApiModel):
    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorResponse(ApiModel):
    error: ErrorDetail


class HealthResponse(ApiModel):
    status: Literal["ok"]
    service: Literal["oge-rice-api"]


class ApiMetadata(ApiModel):
    service: Literal["oge-rice-api"]
    api_version: Literal["v1"]
    result_modes: list[Literal["illustrative"]]
    documentation: str


class ReferenceAreaProperties(ApiModel):
    area_id: str
    revision: int
    name: str
    area_type: Literal["administrative_district", "technical_study_area"]
    administrative_code: str | None
    area_square_metres: float
    quality_status: Literal["illustrative", "unverified", "verified"]
    quality_statement: str
    source_title: str
    source_url: str | None
    boundary_role: Literal["reference_only"]


class ReferenceAreaFeature(ApiModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: dict[str, Any]
    properties: ReferenceAreaProperties


class ReferenceAreaFeatureCollection(ApiModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ReferenceAreaFeature]


class TaskDraftGeometry(ApiModel):
    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]


class TaskDraftAreaSelection(ApiModel):
    method: Literal["reference_area", "rectangle", "polygon"]
    source_area_id: str | None = None
    geometry: TaskDraftGeometry

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if (self.method == "reference_area") != (self.source_area_id is not None):
            raise ValueError("source_area_id is required only for reference_area selections")
        return self


class AnalysisTaskDraftCreate(ApiModel):
    name: str = Field(min_length=2, max_length=80)
    result_mode: Literal["illustrative"] = "illustrative"
    crop_code: Literal["rice"] = "rice"
    analysis_year: int = Field(ge=2020, le=2100)
    season: Literal["single_season_rice", "early_rice", "late_rice"]
    growth_stage_code: str = Field(min_length=1, max_length=50)
    growth_stage_name: str = Field(min_length=1, max_length=100)
    analysis_start: date
    analysis_end: date
    quota_value_m3_per_mu: float = Field(gt=0)
    quota_source: str = Field(min_length=2, max_length=500)
    area: TaskDraftAreaSelection
    created_by: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        if self.analysis_start > self.analysis_end:
            raise ValueError("analysis_start must not be after analysis_end")
        if self.analysis_start.year != self.analysis_year:
            raise ValueError("analysis_start must belong to analysis_year")
        return self


class AnalysisTaskDraftRevisionCreate(AnalysisTaskDraftCreate):
    expected_revision: int = Field(ge=1)
    change_reason: str = Field(min_length=2, max_length=500)


class AnalysisTaskDraftResponse(ApiModel):
    draft_id: str
    revision: int
    status: Literal["draft", "promoted", "withdrawn"]
    name: str
    result_mode: Literal["illustrative"]
    crop_code: Literal["rice"]
    analysis_year: int
    season: Literal["single_season_rice", "early_rice", "late_rice"]
    growth_stage_code: str
    growth_stage_name: str
    analysis_start: date
    analysis_end: date
    quota_value_m3_per_mu: float
    quota_source: str
    area: TaskDraftAreaSelection
    area_square_metres: float
    created_by: str
    created_at: datetime
    changed_at: datetime
    change_reason: str


class AnalysisTaskDraftCollection(ApiModel):
    items: list[AnalysisTaskDraftResponse]
    total: int


class ManagementUnitGeometry(ApiModel):
    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]


class ManagementUnitParent(ApiModel):
    unit_id: str = Field(min_length=1, max_length=100)
    revision: int = Field(ge=1)


class ManagementUnitCreate(ApiModel):
    name: str = Field(min_length=2, max_length=120)
    unit_type: Literal["irrigation_district", "management_zone", "custom"]
    valid_start: date
    valid_end: date
    parent: ManagementUnitParent | None = None
    geometry: ManagementUnitGeometry
    source_title: str = Field(min_length=2, max_length=300)
    source_url: str | None = Field(default=None, max_length=1000)
    quality_status: Literal["unverified", "verified"] = "unverified"
    quality_statement: str = Field(min_length=2, max_length=1000)
    status: Literal["draft", "active"] = "draft"
    changed_by: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_hierarchy_and_period(self) -> Self:
        if self.valid_start > self.valid_end:
            raise ValueError("valid_start must not be after valid_end")
        if (self.unit_type == "irrigation_district") == (self.parent is not None):
            raise ValueError("only non-root management units require a parent")
        return self


class ManagementUnitProperties(ApiModel):
    unit_id: str
    revision: int
    name: str
    unit_type: Literal["irrigation_district", "management_zone", "custom"]
    valid_start: date
    valid_end: date
    root_unit_id: str
    root_revision: int
    parent_unit_id: str | None
    parent_revision: int | None
    area_square_metres: float
    source_title: str
    source_url: str | None
    quality_status: Literal["illustrative", "unverified", "verified"]
    quality_statement: str
    status: Literal["draft", "active", "superseded", "withdrawn"]
    changed_by: str
    changed_at: datetime


class ManagementUnitFeature(ApiModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: dict[str, Any]
    properties: ManagementUnitProperties


class ManagementUnitFeatureCollection(ApiModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[ManagementUnitFeature]
