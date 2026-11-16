"""Read-only map reference areas backed by PostGIS."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from oge_main.api.contracts import (
    ReferenceAreaFeature,
    ReferenceAreaFeatureCollection,
    ReferenceAreaProperties,
)
from oge_main.api.dependencies import get_database_session
from oge_main.api.errors import ApiProblem
from oge_main.infrastructure.database.models import (
    ReferenceAreaVersionRow,
    SpatialAssetRow,
)

router = APIRouter(prefix="/reference-areas", tags=["reference-areas"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


@router.get("", response_model=ReferenceAreaFeatureCollection)
def list_reference_areas(session: DatabaseSession) -> ReferenceAreaFeatureCollection:
    statement = (
        select(
            ReferenceAreaVersionRow,
            SpatialAssetRow.source,
            func.ST_AsGeoJSON(ReferenceAreaVersionRow.geom).label("geometry_json"),
        )
        .join(
            SpatialAssetRow,
            SpatialAssetRow.asset_id == ReferenceAreaVersionRow.boundary_asset_id,
        )
        .where(ReferenceAreaVersionRow.status == "active")
        .order_by(ReferenceAreaVersionRow.name, ReferenceAreaVersionRow.revision)
    )
    try:
        rows = session.execute(statement).all()
    except SQLAlchemyError as error:
        raise ApiProblem(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="reference-area data is temporarily unavailable",
        ) from error

    features = []
    for area, source, geometry_json in rows:
        quality = area.quality
        features.append(
            ReferenceAreaFeature(
                id=f"{area.area_id}@{area.revision}",
                geometry=json.loads(geometry_json),
                properties=ReferenceAreaProperties(
                    area_id=area.area_id,
                    revision=area.revision,
                    name=area.name,
                    area_type=area.area_type,
                    administrative_code=area.administrative_code,
                    quality_status=quality["status"],
                    quality_statement=quality["statement"],
                    source_title=source["title"],
                    source_url=source.get("url"),
                    boundary_role="reference_only",
                ),
            )
        )
    return ReferenceAreaFeatureCollection(features=features)
