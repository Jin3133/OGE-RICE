"""Versioned management-unit import and read API."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Response, status
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.dialects.postgresql.ranges import Range
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from oge_main.api.contracts import (
    ManagementUnitCreate,
    ManagementUnitFeature,
    ManagementUnitFeatureCollection,
    ManagementUnitProperties,
)
from oge_main.api.dependencies import get_database_session
from oge_main.api.errors import ApiProblem
from oge_main.infrastructure.database.models import (
    AuditEventRow,
    IdempotencyRecordRow,
    ManagementUnitVersionRow,
    ResourceHeadRow,
    SpatialAssetRow,
)

router = APIRouter(prefix="/management-units", tags=["management-units"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]
logger = logging.getLogger(__name__)


def _feature(
    row: ManagementUnitVersionRow,
    asset: SpatialAssetRow,
    geometry_json: str,
    area_square_metres: float,
) -> ManagementUnitFeature:
    bounds = row.valid_period
    source = asset.source
    quality = row.quality
    return ManagementUnitFeature(
        id=f"{row.unit_id}@{row.revision}",
        geometry=json.loads(geometry_json),
        properties=ManagementUnitProperties(
            unit_id=row.unit_id,
            revision=row.revision,
            name=row.name,
            unit_type=row.unit_type,
            valid_start=bounds.lower,
            valid_end=bounds.upper - timedelta(days=1),
            root_unit_id=row.root_unit_id,
            root_revision=row.root_revision,
            parent_unit_id=row.parent_unit_id,
            parent_revision=row.parent_revision,
            area_square_metres=area_square_metres,
            source_title=source["title"],
            source_url=source.get("url"),
            quality_status=quality["status"],
            quality_statement=quality["statement"],
            status=row.status,
            changed_by=row.changed_by,
            changed_at=row.changed_at,
        ),
    )


@router.get("", response_model=ManagementUnitFeatureCollection)
def list_management_units(session: DatabaseSession) -> ManagementUnitFeatureCollection:
    statement = (
        select(
            ManagementUnitVersionRow,
            SpatialAssetRow,
            func.ST_AsGeoJSON(ManagementUnitVersionRow.geom).label("geometry_json"),
            func.ST_Area(cast(ManagementUnitVersionRow.geom, Geography)).label("area_m2"),
        )
        .join(
            ResourceHeadRow,
            (ResourceHeadRow.resource_type == "management_unit")
            & (ResourceHeadRow.resource_id == ManagementUnitVersionRow.unit_id)
            & (ResourceHeadRow.current_revision == ManagementUnitVersionRow.revision),
        )
        .join(SpatialAssetRow, SpatialAssetRow.asset_id == ManagementUnitVersionRow.boundary_asset_id)
        .order_by(ManagementUnitVersionRow.changed_at.desc())
    )
    try:
        rows = session.execute(statement).all()
    except SQLAlchemyError as error:
        raise ApiProblem(503, "DATABASE_UNAVAILABLE", "management units could not be loaded") from error
    return ManagementUnitFeatureCollection(
        features=[_feature(row, asset, geometry, area) for row, asset, geometry, area in rows]
    )


@router.post("", response_model=ManagementUnitFeature, status_code=status.HTTP_201_CREATED)
def create_management_unit(
    payload: ManagementUnitCreate,
    response: Response,
    session: DatabaseSession,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=100)],
) -> ManagementUnitFeature:
    request_body = payload.model_dump(mode="json")
    request_hash = hashlib.sha256(
        json.dumps(request_body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    existing = session.get(IdempotencyRecordRow, (payload.changed_by, idempotency_key))
    if existing:
        if existing.request_hash != request_hash:
            raise ApiProblem(409, "IDEMPOTENCY_KEY_REUSED", "idempotency key was reused")
        if existing.status == "completed" and existing.response_body:
            response.status_code = existing.response_status or status.HTTP_201_CREATED
            return ManagementUnitFeature.model_validate(existing.response_body)
        raise ApiProblem(409, "REQUEST_IN_PROGRESS", "matching request is still processing")

    geometry_json = json.dumps(payload.geometry.model_dump(mode="json"))
    raw_geometry = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geometry_json), 4326)
    normalized_geometry = func.ST_Multi(raw_geometry)
    geometry_check = session.execute(
        select(
            func.ST_IsValid(normalized_geometry).label("valid"),
            func.GeometryType(normalized_geometry).label("geometry_type"),
            func.ST_Area(cast(normalized_geometry, Geography)).label("area_m2"),
        )
    ).one()
    if not geometry_check.valid or geometry_check.geometry_type != "MULTIPOLYGON":
        raise ApiProblem(422, "INVALID_MANAGEMENT_UNIT_GEOMETRY", "boundary must be a valid polygon")
    if geometry_check.area_m2 <= 0:
        raise ApiProblem(422, "EMPTY_MANAGEMENT_UNIT_GEOMETRY", "boundary must have positive area")

    parent = None
    if payload.parent:
        parent = session.get(
            ManagementUnitVersionRow,
            (payload.parent.unit_id, payload.parent.revision),
        )
        if parent is None or parent.status not in {"draft", "active"}:
            raise ApiProblem(422, "PARENT_MANAGEMENT_UNIT_NOT_FOUND", "parent version is unavailable")
        allowed_parent_types = {
            "management_zone": {"irrigation_district"},
            "custom": {"irrigation_district", "management_zone"},
        }
        if parent.unit_type not in allowed_parent_types[payload.unit_type]:
            raise ApiProblem(422, "INVALID_MANAGEMENT_UNIT_HIERARCHY", "parent type is not allowed")
        if payload.valid_start < parent.valid_period.lower or payload.valid_end >= parent.valid_period.upper:
            raise ApiProblem(422, "VALID_PERIOD_OUTSIDE_PARENT", "valid period must be within the parent period")
        if not session.scalar(func.ST_CoveredBy(normalized_geometry, parent.geom)):
            raise ApiProblem(422, "BOUNDARY_OUTSIDE_PARENT", "child boundary must be covered by its parent")

    now = datetime.now(UTC)
    unit_id = f"unit_{uuid4().hex}"
    asset_id = f"asset_{uuid4().hex}"
    revision = 1
    root_unit_id = unit_id if parent is None else parent.root_unit_id
    root_revision = revision if parent is None else parent.root_revision
    valid_period = Range(
        payload.valid_start,
        payload.valid_end + timedelta(days=1),
        bounds="[)",
    )
    asset = SpatialAssetRow(
        asset_id=asset_id,
        href=f"database://management-units/{unit_id}/versions/{revision}/boundary",
        media_type="application/geo+json",
        roles=["boundary"],
        crs="EPSG:4326",
        checksum_sha256=hashlib.sha256(geometry_json.encode()).hexdigest(),
        created_at=now,
        source={"title": payload.source_title, "url": payload.source_url},
    )
    row = ManagementUnitVersionRow(
        unit_id=unit_id,
        revision=revision,
        name=payload.name,
        unit_type=payload.unit_type,
        boundary_asset_id=asset_id,
        valid_period=valid_period,
        root_unit_id=root_unit_id,
        root_revision=root_revision,
        parent_unit_id=parent.unit_id if parent else None,
        parent_revision=parent.revision if parent else None,
        geom=normalized_geometry,
        quality={"status": payload.quality_status, "statement": payload.quality_statement},
        previous_unit_id=None,
        previous_revision=None,
        status=payload.status,
        change_reason="导入管理单元初始版本",
        changed_by=payload.changed_by,
        changed_at=now,
        feedback_id=None,
    )
    session.add(asset)
    session.flush()
    session.add(row)
    session.add(
        ResourceHeadRow(
            resource_type="management_unit",
            resource_id=unit_id,
            current_revision=revision,
            updated_at=now,
        )
    )
    result = _feature(row, asset, geometry_json, geometry_check.area_m2)
    session.add(
        AuditEventRow(
            event_id=f"audit_{uuid4().hex}",
            occurred_at=now,
            actor_id=payload.changed_by,
            request_id=idempotency_key,
            action="management_unit.created",
            resource_type="management_unit",
            resource_id=unit_id,
            resource_revision=revision,
            summary={"name": payload.name, "unit_type": payload.unit_type, "status": payload.status},
        )
    )
    session.add(
        IdempotencyRecordRow(
            actor_id=payload.changed_by,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            status="completed",
            response_status=status.HTTP_201_CREATED,
            resource_type="management_unit",
            resource_id=unit_id,
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
        logger.exception("management-unit persistence conflict")
        raise ApiProblem(409, "MANAGEMENT_UNIT_CONFLICT", "management unit conflicts with stored data") from error
    except SQLAlchemyError as error:
        session.rollback()
        raise ApiProblem(503, "DATABASE_UNAVAILABLE", "management unit could not be stored") from error
    response.headers["Location"] = f"/api/v1/management-units/{unit_id}/versions/{revision}"
    return result
