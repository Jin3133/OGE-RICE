"""Stable HTTP-only contracts that do not belong to the business domain."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
