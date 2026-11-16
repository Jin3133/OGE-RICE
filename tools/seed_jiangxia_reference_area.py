"""Load the public Jiangxia administrative boundary as a reference-only map area."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select

from oge_main.infrastructure.database.models import (
    ReferenceAreaVersionRow,
    ResourceHeadRow,
    SpatialAssetRow,
)
from oge_main.infrastructure.database.session import (
    DatabaseSettings,
    create_session_factory,
)

AREA_ID = "reference-area.cn.hubei.wuhan.jiangxia.420115"
ASSET_ID = "asset.reference-area.jiangxia-420115.boundary.v1"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "boundary",
        type=Path,
        help="WGS84 Jiangxia GeoJSON from the oge-rice boundary inventory",
    )
    return parser.parse_args()


def main() -> None:
    boundary_path = arguments().boundary.resolve()
    payload_bytes = boundary_path.read_bytes()
    payload = json.loads(payload_bytes)
    if payload.get("type") != "FeatureCollection" or len(payload.get("features", [])) != 1:
        raise ValueError("boundary must contain exactly one GeoJSON feature")
    feature = payload["features"][0]
    geometry = feature["geometry"]
    if geometry.get("type") != "MultiPolygon":
        raise ValueError("Jiangxia reference boundary must be a MultiPolygon")
    properties = feature.get("properties", {})
    if str(properties.get("adcode")) != "420115":
        raise ValueError("boundary administrative code must be 420115")

    checksum = hashlib.sha256(payload_bytes).hexdigest()
    now = datetime.now(UTC)
    factory = create_session_factory(DatabaseSettings.from_environment())
    with factory.begin() as session:
        existing = session.get(ReferenceAreaVersionRow, (AREA_ID, 1))
        if existing is not None:
            asset = session.get(SpatialAssetRow, ASSET_ID)
            if asset is None or asset.checksum_sha256 != checksum:
                raise RuntimeError("existing reference area does not match the boundary checksum")
            print(f"reference area already loaded: {AREA_ID}@1")
            return

        asset = session.get(SpatialAssetRow, ASSET_ID)
        if asset is None:
            session.add(
                SpatialAssetRow(
                    asset_id=ASSET_ID,
                    href="oge-rice/data/boundaries/jiangxia_420115_wgs84.geojson",
                    media_type="application/geo+json",
                    roles=["boundary", "overview"],
                    crs="EPSG:4326",
                    checksum_sha256=checksum,
                    created_at=now,
                    source={
                        "title": "DataV.GeoAtlas 江夏区行政边界",
                        "publisher": "阿里云 DataV.GeoAtlas",
                        "url": "https://geo.datav.aliyun.com/areas_v3/bound/420115.json",
                        "publication_year": None,
                        "retrieved_at": "2026-11-04",
                    },
                )
            )
            session.flush()

        source_geometry = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)), 4326)
        repaired_geometry = func.ST_Multi(
            func.ST_CollectionExtract(func.ST_MakeValid(source_geometry), 3)
        )
        validation = session.execute(
            select(
                func.ST_IsValid(source_geometry).label("source_valid"),
                func.ST_IsValidReason(source_geometry).label("source_reason"),
                func.ST_IsValid(repaired_geometry).label("repaired_valid"),
                func.GeometryType(repaired_geometry).label("repaired_type"),
                func.ST_Area(cast(source_geometry, Geography)).label("source_area_m2"),
                func.ST_Area(cast(repaired_geometry, Geography)).label("repaired_area_m2"),
                func.ST_Area(
                    cast(
                        func.ST_SymDifference(source_geometry, repaired_geometry),
                        Geography,
                    )
                ).label("difference_area_m2"),
            )
        ).one()
        if validation.source_valid:
            normalized_geometry = source_geometry
            repair_statement = "原始公开边界通过PostGIS几何有效性检查。"
        else:
            if not validation.repaired_valid or validation.repaired_type != "MULTIPOLYGON":
                raise ValueError("public boundary cannot be normalized to a valid MultiPolygon")
            if validation.difference_area_m2 > 1.0:
                raise ValueError("geometry repair changes more than one square metre")
            normalized_geometry = repaired_geometry
            repair_statement = (
                f"原始公开边界存在{validation.source_reason}；入库时显式采用"
                "ST_MakeValid并提取面要素，修复前后地理面积一致。"
            )

        session.add(
            ReferenceAreaVersionRow(
                area_id=AREA_ID,
                revision=1,
                name="武汉市江夏区",
                area_type="administrative_district",
                administrative_code="420115",
                boundary_asset_id=ASSET_ID,
                geom=normalized_geometry,
                quality={
                    "status": "illustrative",
                    "statement": (
                        "公开行政区可视化边界，仅用于技术试验范围定位；"
                        "不代表灌区边界或实际供水服务范围。" + repair_statement
                    ),
                    "reviewed_by": None,
                    "reviewed_at": None,
                },
                previous_area_id=None,
                previous_revision=None,
                status="active",
                change_reason="建立真实地图参考范围并记录公开边界几何规范化过程",
                changed_by="team.seed",
                changed_at=now,
            )
        )
        session.add(
            ResourceHeadRow(
                resource_type="reference_area",
                resource_id=AREA_ID,
                current_revision=1,
                updated_at=now,
            )
        )
    print(f"loaded reference area: {AREA_ID}@1 ({checksum})")
    print(repair_statement)


if __name__ == "__main__":
    main()
