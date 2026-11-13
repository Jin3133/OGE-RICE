"""Minimal OGE access test for one Wuhan-1 LJ3II_MSS scene.

Expected result on 2026-11-04 for the current account:
    脚本解析失败：数据产品[LJ3II_MSS]无使用权限

Keep this script as a reproducible permission check. It does not download data.
"""

import oge


CONFIG = {
    "product_id": "LJ3II_MSS",
    "coverage_id": "LJ3II_MSS_E114.25_N31.20_20251008_L1A_001",
    "center": (114.2471, 31.1860),
    "zoom": 11,
    "layer_name": "HGZ_WUHAN1_PERMISSION_TEST",
}


oge.initialize()
service = oge.Service()

image = service.getCoverage(
    coverageID=CONFIG["coverage_id"],
    productID=CONFIG["product_id"],
)
image.getMap(CONFIG["layer_name"])
oge.mapclient.centerMap(*CONFIG["center"], CONFIG["zoom"])
