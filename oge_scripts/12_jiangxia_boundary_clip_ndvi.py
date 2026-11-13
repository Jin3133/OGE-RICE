"""Use the uploaded Jiangxia boundary to clip one Sentinel-2 scene and map NDVI.

Run this single-scene probe before expanding the same boundary workflow to the
fixed six-scene collection.  The uploaded boundary is already in EPSG:32650,
matching tile T50RKU.
"""

import oge


CONFIG = {
    "scene_id": "T50RKU_20251005T025529",
    "product_id": "S2_MSIL2A",
    "boundary_id": "myData/jiangxia_420115_utm50n.geojson",
    "ndvi_layer": "HGZ_JIANGXIA_CLIP_NDVI_20251005",
    "map_center": (114.31, 30.25),
    "zoom": 10,
}


oge.initialize()
service = oge.Service()

boundary = service.getFeatureCollection(CONFIG["boundary_id"])

image = service.getCoverage(
    coverageID=CONFIG["scene_id"],
    productID=CONFIG["product_id"],
)

clipped = service.getProcess("Coverage.clip").execute(image, boundary)
ndvi = service.getProcess("Coverage.normalizedDifference").execute(
    clipped,
    ["B08", "B04"],
)

ndvi.styles(
    {
        "min": -1,
        "max": 1,
        "palette": ["#8c510a", "#f6e8c3", "#c7eae5", "#01665e"],
    }
).getMap(CONFIG["ndvi_layer"])

oge.mapclient.centerMap(
    CONFIG["map_center"][0],
    CONFIG["map_center"][1],
    CONFIG["zoom"],
)
