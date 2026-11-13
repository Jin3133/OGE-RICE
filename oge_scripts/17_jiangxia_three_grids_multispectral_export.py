"""Export 15 four-band Sentinel-2 chips for algorithm development.

Band order is B02, B03, B04, B08. All four bands are native 10 m Sentinel-2
bands, so the exported stacks align with the existing 10 m NDVI assets.
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
        image = service.getCoverage(coverageID=scene_id, productID="S2_MSIL2A")
        clipped = service.getProcess("Coverage.clip").execute(image, geometry)
        multispectral = service.getProcess("Coverage.selectBands").execute(
            clipped,
            ["B02", "B03", "B04", "B08"],
        )
        multispectral.export(f"HGZ_{grid_id}_MS4_{date_token}")
