"""Create 15 persistent NDVI tasks for three Jiangxia grids and five dates.

Run once in OGE. Each ``export`` call creates a task-panel item. For every item,
set EPSG:32650, 10 m/px and TIF. Do not type the .tif extension in the filename.
"""

import oge


oge.initialize()
service = oge.Service()

GRIDS = {
    "JX5K_R03C06": [235000.0, 3325000.0, 240000.0, 3330000.0],
    "JX5K_R07C05": [230000.0, 3345000.0, 235000.0, 3350000.0],
    "JX5K_R10C10": [255000.0, 3360000.0, 260000.0, 3365000.0],
}

SCENES = {
    "20250501": "T50RKU_20250501T030529",
    "20250511": "T50RKU_20250511T030529",
    "20250705": "T50RKU_20250705T030601",
    "20250816": "T50RKU_20250816T025529",
    "20251005": "T50RKU_20251005T025529",
}

for grid_id, (xmin, ymin, xmax, ymax) in GRIDS.items():
    coordinates = [[[
        [xmin, ymin],
        [xmax, ymin],
        [xmax, ymax],
        [xmin, ymax],
        [xmin, ymin],
    ]]]
    geometry = service.getProcess("Geometry.MultiPolygon").execute(
        coordinates=coordinates,
        crs="EPSG:32650",
        geodesic="false",
    )
    for date_token, scene_id in SCENES.items():
        if grid_id == "JX5K_R07C05" and date_token == "20251005":
            # This asset was persisted during the single-grid export validation.
            continue
        image = service.getCoverage(coverageID=scene_id, productID="S2_MSIL2A")
        clipped = service.getProcess("Coverage.clip").execute(image, geometry)
        ndvi = service.getProcess("Coverage.normalizedDifference").execute(
            clipped,
            ["B08", "B04"],
        )
        ndvi.export(f"HGZ_{grid_id}_NDVI_{date_token}")
