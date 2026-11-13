"""Export candidate Sentinel-2 scenes over one Jiangxia grid for source QC.

Only candidates that produce non-empty MS4 and NDVI GeoTIFFs will be promoted
to the three-grid labeling dataset.
"""

import oge


oge.initialize()
service = oge.Service()

GRID_ID = "JX5K_R07C05"
XMIN, YMIN, XMAX, YMAX = [230000.0, 3345000.0, 235000.0, 3350000.0]

CANDIDATES = {
    "20250418": "T50RKU_20250418T025529",
    "20250428": "T50RKU_20250428T025529",
    "20250605": "T50RKU_20250605T030541",
}

coordinates = [[[
    [XMIN, YMIN],
    [XMAX, YMIN],
    [XMAX, YMAX],
    [XMIN, YMAX],
    [XMIN, YMIN],
]]]
geometry = service.getProcess("Geometry.MultiPolygon").execute(
    coordinates=coordinates,
    crs="EPSG:32650",
    geodesic="false",
)

for date_token, scene_id in CANDIDATES.items():
    image = service.getCoverage(coverageID=scene_id, productID="S2_MSIL2A")
    clipped = service.getProcess("Coverage.clip").execute(image, geometry)
    ms4 = service.getProcess("Coverage.selectBands").execute(
        clipped,
        ["B02", "B03", "B04", "B08"],
    )
    red = service.getProcess("Coverage.selectBands").execute(clipped, ["B04"])
    nir = service.getProcess("Coverage.selectBands").execute(clipped, ["B08"])
    ndvi = service.getProcess("Coverage.normalizedDifference").execute(nir, red)

    ms4.export(f"HGZ_QC_{GRID_ID}_MS4_{date_token}")
    ndvi.export(f"HGZ_QC_{GRID_ID}_NDVI_{date_token}")
