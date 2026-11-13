"""Embed a validated GeoJSON geometry into an OGE development-center script."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/boundaries/jiangxia_420115_utm50n.geojson"
TARGET = ROOT / "oge_scripts/13_jiangxia_embedded_boundary_clip_ndvi.py"

payload = json.loads(SOURCE.read_text(encoding="utf-8"))
coordinates = payload["features"][0]["geometry"]["coordinates"]

script = f'''"""Clip Sentinel-2 with the verified Jiangxia EPSG:32650 boundary.

Generated from data/boundaries/jiangxia_420115_utm50n.geojson because the OGE
runtime does not reliably accept an uploaded FeatureCollection in Coverage.clip.
"""

import oge


BOUNDARY_COORDINATES = {repr(coordinates)}


oge.initialize()
service = oge.Service()

boundary = service.getProcess("Geometry.MultiPolygon").execute(
    coordinates=BOUNDARY_COORDINATES,
    crs="EPSG:32650",
    geodesic="false",
)
image = service.getCoverage(
    coverageID="T50RKU_20251005T025529",
    productID="S2_MSIL2A",
)
clipped = service.getProcess("Coverage.clip").execute(image, boundary)
ndvi = service.getProcess("Coverage.normalizedDifference").execute(
    clipped,
    ["B08", "B04"],
)
ndvi.styles(
    {{
        "min": -1,
        "max": 1,
        "palette": ["#8c510a", "#f6e8c3", "#c7eae5", "#01665e"],
    }}
).getMap("HGZ_JIANGXIA_CLIP_NDVI_20251005")

oge.mapclient.centerMap(114.31, 30.25, 10)
'''

TARGET.write_text(script, encoding="utf-8")
print(TARGET)
