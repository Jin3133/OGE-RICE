"""Reproject a GeoJSON from WGS84 to UTM zone 50N without third-party packages."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def wgs84_to_utm50n(lon: float, lat: float) -> list[float]:
    a = 6_378_137.0
    flattening = 1 / 298.257223563
    e2 = flattening * (2 - flattening)
    ep2 = e2 / (1 - e2)
    k0 = 0.9996
    zone = 50

    phi = math.radians(lat)
    lam = math.radians(lon)
    lam0 = math.radians((zone - 1) * 6 - 180 + 3)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    tan_phi = math.tan(phi)

    n = a / math.sqrt(1 - e2 * sin_phi**2)
    t = tan_phi**2
    c = ep2 * cos_phi**2
    aa = cos_phi * (lam - lam0)
    m = a * (
        (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * phi
        - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * phi)
        + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * phi)
        - (35 * e2**3 / 3072) * math.sin(6 * phi)
    )
    easting = 500_000 + k0 * n * (
        aa
        + (1 - t + c) * aa**3 / 6
        + (5 - 18 * t + t**2 + 72 * c - 58 * ep2) * aa**5 / 120
    )
    northing = k0 * (
        m
        + n
        * tan_phi
        * (
            aa**2 / 2
            + (5 - t + 9 * c + 4 * c**2) * aa**4 / 24
            + (61 - 58 * t + t**2 + 600 * c - 330 * ep2) * aa**6 / 720
        )
    )
    return [round(easting, 3), round(northing, 3)]


def transform_coordinates(value):
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        return wgs84_to_utm50n(value[0], value[1]) + value[2:]
    return [transform_coordinates(item) for item in value]


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: reproject_wgs84_to_utm50n.py INPUT.geojson OUTPUT.geojson")
    source = Path(sys.argv[1])
    target = Path(sys.argv[2])
    data = json.loads(source.read_text(encoding="utf-8"))
    for feature in data["features"]:
        feature["geometry"]["coordinates"] = transform_coordinates(
            feature["geometry"]["coordinates"]
        )
        feature.setdefault("properties", {})["source_crs"] = "EPSG:4326"
        feature["properties"]["target_crs"] = "EPSG:32650"
    data["crs"] = {
        "type": "name",
        "properties": {"name": "urn:ogc:def:crs:EPSG::32650"},
    }
    target.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
