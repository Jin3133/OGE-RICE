"""Persist the verified Jiangxia grid NDVI as a GeoTIFF batch result in OGE."""

import oge


oge.initialize()
service = oge.Service()

image = service.getCoverage(
    coverageID="T50RKU_20251005T025529",
    productID="S2_MSIL2A",
)

coordinates = [[[
    [230000.0, 3345000.0],
    [235000.0, 3345000.0],
    [235000.0, 3350000.0],
    [230000.0, 3350000.0],
    [230000.0, 3345000.0],
]]]

geometry = service.getProcess("Geometry.MultiPolygon").execute(
    coordinates=coordinates,
    crs="EPSG:32650",
    geodesic="false",
)

clipped = service.getProcess("Coverage.clip").execute(image, geometry)
ndvi = service.getProcess("Coverage.normalizedDifference").execute(
    clipped,
    ["B08", "B04"],
)

# This creates a task in the OGE task panel. Confirm EPSG:32650, 10 m/px and TIF
# in the task dialog before starting the asynchronous export.
ndvi.export("HGZ_JX5K_R07C05_NDVI_20251005")
