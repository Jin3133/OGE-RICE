"""Durable planning drafts created before versioned analysis inputs exist."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Response, status
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from oge_main.api.contracts import (
    AnalysisTaskDraftCollection,
    AnalysisTaskDraftCreate,
    AnalysisTaskDraftResponse,
    AnalysisTaskDraftRevisionCreate,
    TaskDraftAreaSelection,
    TaskDraftGeometry,
)
from oge_main.api.dependencies import get_database_session
from oge_main.api.errors import ApiProblem
from oge_main.infrastructure.database.models import (
    AnalysisTaskDraftVersionRow,
    AuditEventRow,
    IdempotencyRecordRow,
    ReferenceAreaVersionRow,
    ResourceHeadRow,
)

router = APIRouter(prefix="/analysis-task-drafts", tags=["analysis-task-drafts"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


def _response(row: AnalysisTaskDraftVersionRow, geometry: dict) -> AnalysisTaskDraftResponse:
    return AnalysisTaskDraftResponse(
        draft_id=row.draft_id,
        revision=row.revision,
        status=row.status,
        name=row.name,
        result_mode=row.result_mode,
        crop_code=row.crop_code,
        analysis_year=row.analysis_year,
        season=row.season,
        growth_stage_code=row.growth_stage_code,
        growth_stage_name=row.growth_stage_name,
        analysis_start=row.analysis_start,
        analysis_end=row.analysis_end,
        quota_value_m3_per_mu=row.quota_value_m3_per_mu,
        quota_source=row.quota_source,
        area=TaskDraftAreaSelection(
            method=row.area_method,
            source_area_id=row.source_area_id,
            geometry=TaskDraftGeometry.model_validate(geometry),
        ),
        area_square_metres=row.area_square_metres,
        created_by=row.created_by,
        created_at=row.created_at,
        changed_at=row.changed_at,
        change_reason=row.change_reason,
    )


@router.get("", response_model=AnalysisTaskDraftCollection)
def list_task_drafts(session: DatabaseSession) -> AnalysisTaskDraftCollection:
    statement = (
        select(
            AnalysisTaskDraftVersionRow,
            func.ST_AsGeoJSON(AnalysisTaskDraftVersionRow.geom).label("geometry_json"),
        )
        .join(
            ResourceHeadRow,
            (ResourceHeadRow.resource_type == "analysis_task_draft")
            & (ResourceHeadRow.resource_id == AnalysisTaskDraftVersionRow.draft_id)
            & (ResourceHeadRow.current_revision == AnalysisTaskDraftVersionRow.revision),
        )
        .order_by(AnalysisTaskDraftVersionRow.changed_at.desc())
        .limit(50)
    )
    try:
        rows = session.execute(statement).all()
    except SQLAlchemyError as error:
        raise ApiProblem(503, "DATABASE_UNAVAILABLE", "task drafts could not be loaded") from error
    items = [_response(row, json.loads(geometry_json)) for row, geometry_json in rows]
    return AnalysisTaskDraftCollection(items=items, total=len(items))


@router.post("", response_model=AnalysisTaskDraftResponse, status_code=status.HTTP_201_CREATED)
def create_task_draft(
    payload: AnalysisTaskDraftCreate,
    response: Response,
    session: DatabaseSession,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
) -> AnalysisTaskDraftResponse:
    actor = payload.created_by
    request_body = payload.model_dump(mode="json")
    request_hash = hashlib.sha256(
        json.dumps(request_body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    existing = session.get(IdempotencyRecordRow, (actor, idempotency_key))
    if existing:
        if existing.request_hash != request_hash:
            raise ApiProblem(409, "IDEMPOTENCY_KEY_REUSED", "idempotency key was reused")
        if existing.status == "completed" and existing.response_body:
            response.status_code = existing.response_status or status.HTTP_201_CREATED
            return AnalysisTaskDraftResponse.model_validate(existing.response_body)
        raise ApiProblem(409, "REQUEST_IN_PROGRESS", "matching request is still processing")

    geometry_json = json.dumps(payload.area.geometry.model_dump(mode="json"))
    raw_geometry = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geometry_json), 4326)
    normalized_geometry = func.ST_Multi(raw_geometry)

    if payload.area.method == "reference_area":
        source_area = session.scalars(
            select(ReferenceAreaVersionRow).where(
                ReferenceAreaVersionRow.area_id == payload.area.source_area_id,
                ReferenceAreaVersionRow.status == "active",
            )
        ).first()
        if source_area is None:
            raise ApiProblem(422, "REFERENCE_AREA_NOT_FOUND", "reference area is not active")
        if not session.scalar(func.ST_Equals(normalized_geometry, source_area.geom)):
            raise ApiProblem(
                422,
                "REFERENCE_AREA_GEOMETRY_MISMATCH",
                "submitted geometry does not match the reference area",
            )

    geometry_check = session.execute(
        select(
            func.ST_IsValid(normalized_geometry).label("valid"),
            func.GeometryType(normalized_geometry).label("geometry_type"),
            func.ST_Area(cast(normalized_geometry, Geography)).label("area_m2"),
        )
    ).one()
    if not geometry_check.valid or geometry_check.geometry_type != "MULTIPOLYGON":
        raise ApiProblem(422, "INVALID_ANALYSIS_AREA", "analysis area must be a valid polygon")
    if geometry_check.area_m2 <= 0:
        raise ApiProblem(422, "EMPTY_ANALYSIS_AREA", "analysis area must have positive area")

    now = datetime.now(UTC)
    draft_id = f"draft_{uuid4().hex}"
    row = AnalysisTaskDraftVersionRow(
        draft_id=draft_id,
        revision=1,
        name=payload.name,
        result_mode=payload.result_mode,
        crop_code=payload.crop_code,
        analysis_year=payload.analysis_year,
        season=payload.season,
        growth_stage_code=payload.growth_stage_code,
        growth_stage_name=payload.growth_stage_name,
        analysis_start=payload.analysis_start,
        analysis_end=payload.analysis_end,
        quota_value_m3_per_mu=payload.quota_value_m3_per_mu,
        quota_source=payload.quota_source,
        area_method=payload.area.method,
        source_area_id=payload.area.source_area_id,
        geom=normalized_geometry,
        area_square_metres=geometry_check.area_m2,
        status="draft",
        previous_draft_id=None,
        previous_revision=None,
        created_by=actor,
        created_at=now,
        changed_at=now,
        change_reason="创建分析任务规划草稿",
    )
    session.add(row)
    session.add(
        ResourceHeadRow(
            resource_type="analysis_task_draft",
            resource_id=draft_id,
            current_revision=1,
            updated_at=now,
        )
    )
    session.add(
        AuditEventRow(
            event_id=f"audit_{uuid4().hex}",
            occurred_at=now,
            actor_id=actor,
            request_id=idempotency_key,
            action="analysis_task_draft.created",
            resource_type="analysis_task_draft",
            resource_id=draft_id,
            resource_revision=1,
            summary={"name": payload.name, "result_mode": payload.result_mode},
        )
    )
    result = _response(row, payload.area.geometry.model_dump(mode="json"))
    session.add(
        IdempotencyRecordRow(
            actor_id=actor,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="completed",
            response_status=status.HTTP_201_CREATED,
            resource_type="analysis_task_draft",
            resource_id=draft_id,
            resource_revision=1,
            response_body=result.model_dump(mode="json"),
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
    )
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApiProblem(
            409, "DRAFT_CONFLICT", "analysis task draft conflicts with stored data"
        ) from error
    except SQLAlchemyError as error:
        session.rollback()
        raise ApiProblem(503, "DATABASE_UNAVAILABLE", "task draft could not be stored") from error
    response.headers["Location"] = f"/api/v1/analysis-task-drafts/{draft_id}/versions/1"
    return result


@router.post(
    "/{draft_id}/versions",
    response_model=AnalysisTaskDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task_draft_revision(
    draft_id: str,
    payload: AnalysisTaskDraftRevisionCreate,
    response: Response,
    session: DatabaseSession,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
) -> AnalysisTaskDraftResponse:
    actor = payload.created_by
    request_body = payload.model_dump(mode="json")
    request_hash = hashlib.sha256(
        json.dumps(request_body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    existing = session.get(IdempotencyRecordRow, (actor, idempotency_key))
    if existing:
        if existing.request_hash != request_hash:
            raise ApiProblem(409, "IDEMPOTENCY_KEY_REUSED", "idempotency key was reused")
        if existing.status == "completed" and existing.response_body:
            response.status_code = existing.response_status or status.HTTP_201_CREATED
            return AnalysisTaskDraftResponse.model_validate(existing.response_body)
        raise ApiProblem(409, "REQUEST_IN_PROGRESS", "matching request is still processing")

    head = session.scalar(
        select(ResourceHeadRow)
        .where(
            ResourceHeadRow.resource_type == "analysis_task_draft",
            ResourceHeadRow.resource_id == draft_id,
        )
        .with_for_update()
    )
    if head is None:
        raise ApiProblem(404, "TASK_DRAFT_NOT_FOUND", "analysis task draft was not found")
    if head.current_revision != payload.expected_revision:
        raise ApiProblem(
            409,
            "VERSION_CONFLICT",
            "analysis task draft has a newer revision",
            details={
                "expected_revision": payload.expected_revision,
                "current_revision": head.current_revision,
            },
        )
    previous = session.get(AnalysisTaskDraftVersionRow, (draft_id, payload.expected_revision))
    if previous is None or previous.status != "draft":
        raise ApiProblem(409, "DRAFT_NOT_EDITABLE", "analysis task draft is not editable")

    geometry_json = json.dumps(payload.area.geometry.model_dump(mode="json"))
    raw_geometry = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geometry_json), 4326)
    normalized_geometry = func.ST_Multi(raw_geometry)
    if payload.area.method == "reference_area":
        source_area = session.scalars(
            select(ReferenceAreaVersionRow).where(
                ReferenceAreaVersionRow.area_id == payload.area.source_area_id,
                ReferenceAreaVersionRow.status == "active",
            )
        ).first()
        if source_area is None:
            raise ApiProblem(422, "REFERENCE_AREA_NOT_FOUND", "reference area is not active")
        if not session.scalar(func.ST_Equals(normalized_geometry, source_area.geom)):
            raise ApiProblem(
                422,
                "REFERENCE_AREA_GEOMETRY_MISMATCH",
                "submitted geometry does not match the reference area",
            )
    geometry_check = session.execute(
        select(
            func.ST_IsValid(normalized_geometry).label("valid"),
            func.GeometryType(normalized_geometry).label("geometry_type"),
            func.ST_Area(cast(normalized_geometry, Geography)).label("area_m2"),
        )
    ).one()
    if not geometry_check.valid or geometry_check.geometry_type != "MULTIPOLYGON":
        raise ApiProblem(422, "INVALID_ANALYSIS_AREA", "analysis area must be a valid polygon")
    if geometry_check.area_m2 <= 0:
        raise ApiProblem(422, "EMPTY_ANALYSIS_AREA", "analysis area must have positive area")

    now = datetime.now(UTC)
    revision = head.current_revision + 1
    row = AnalysisTaskDraftVersionRow(
        draft_id=draft_id,
        revision=revision,
        name=payload.name,
        result_mode=payload.result_mode,
        crop_code=payload.crop_code,
        analysis_year=payload.analysis_year,
        season=payload.season,
        growth_stage_code=payload.growth_stage_code,
        growth_stage_name=payload.growth_stage_name,
        analysis_start=payload.analysis_start,
        analysis_end=payload.analysis_end,
        quota_value_m3_per_mu=payload.quota_value_m3_per_mu,
        quota_source=payload.quota_source,
        area_method=payload.area.method,
        source_area_id=payload.area.source_area_id,
        geom=normalized_geometry,
        area_square_metres=geometry_check.area_m2,
        status="draft",
        previous_draft_id=draft_id,
        previous_revision=payload.expected_revision,
        created_by=previous.created_by,
        created_at=previous.created_at,
        changed_at=now,
        change_reason=payload.change_reason,
    )
    session.add(row)
    head.current_revision = revision
    head.updated_at = now
    session.add(
        AuditEventRow(
            event_id=f"audit_{uuid4().hex}",
            occurred_at=now,
            actor_id=actor,
            request_id=idempotency_key,
            action="analysis_task_draft.revised",
            resource_type="analysis_task_draft",
            resource_id=draft_id,
            resource_revision=revision,
            summary={
                "previous_revision": payload.expected_revision,
                "change_reason": payload.change_reason,
            },
        )
    )
    result = _response(row, payload.area.geometry.model_dump(mode="json"))
    session.add(
        IdempotencyRecordRow(
            actor_id=actor,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="completed",
            response_status=status.HTTP_201_CREATED,
            resource_type="analysis_task_draft",
            resource_id=draft_id,
            resource_revision=revision,
            response_body=result.model_dump(mode="json"),
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
    )
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApiProblem(
            409, "VERSION_CONFLICT", "analysis task draft revision conflicts"
        ) from error
    except SQLAlchemyError as error:
        session.rollback()
        raise ApiProblem(503, "DATABASE_UNAVAILABLE", "task draft could not be stored") from error
    response.headers["Location"] = f"/api/v1/analysis-task-drafts/{draft_id}/versions/{revision}"
    return result


@router.get("/{draft_id}/versions/{revision}", response_model=AnalysisTaskDraftResponse)
def get_task_draft(
    draft_id: str, revision: int, session: DatabaseSession
) -> AnalysisTaskDraftResponse:
    statement = select(
        AnalysisTaskDraftVersionRow,
        func.ST_AsGeoJSON(AnalysisTaskDraftVersionRow.geom).label("geometry_json"),
    ).where(
        AnalysisTaskDraftVersionRow.draft_id == draft_id,
        AnalysisTaskDraftVersionRow.revision == revision,
    )
    result = session.execute(statement).one_or_none()
    if result is None:
        raise ApiProblem(404, "TASK_DRAFT_NOT_FOUND", "analysis task draft was not found")
    row, geometry_json = result
    return _response(row, json.loads(geometry_json))
