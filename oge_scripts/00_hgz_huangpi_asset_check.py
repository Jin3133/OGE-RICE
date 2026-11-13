"""Minimal OGE read check for the Huangpi representative dataset.

Copy this script to the OGE development center. Change only the CONFIG values when
validating another scene. A successful map layer proves catalog-level access; band and
footprint checks are handled by subsequent screening scripts.
"""

import oge


CONFIG = {
    "product_id": "LJ3II_MSS",
    "coverage_id": "LJ3II_MSS_E114.25_N31.20_20251008_L1A_001",
    "layer_name": "HGZ_HP_WEST_NORTH_HILL_RAW",
    "center_lon": 114.25,
    "center_lat": 31.20,
    "zoom": 11,
}


oge.initialize()
service = oge.Service()

image = service.getCoverage(
    coverageID=CONFIG["coverage_id"],
    productID=CONFIG["product_id"],
)
image.getMap(CONFIG["layer_name"])
oge.mapclient.centerMap(
    CONFIG["center_lon"],
    CONFIG["center_lat"],
    CONFIG["zoom"],
)
