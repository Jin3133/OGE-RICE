"""逐景检查 Sentinel-2 读取、B04/B08 波段和 NDVI 计算链路。

在 OGE 开发中心逐次修改 CONFIG，单景运行。不要一次发布多个地图图层，
避免交互式会话超时导致无法判断具体失败场景。
"""

import oge


CONFIG = {
    "scene_id": "T50RKU_20251005T025529",
    "product_id": "S2_MSIL2A",
    "layer_name": "HGZ_HP_NDVI_20251005",
    "center_lon": 114.30,
    "center_lat": 30.88,
    "zoom": 10,
}


oge.initialize()
service = oge.Service()

image = service.getCoverage(
    coverageID=CONFIG["scene_id"],
    productID=CONFIG["product_id"],
)

ndvi = service.getProcess("Coverage.normalizedDifference").execute(
    image,
    ["B08", "B04"],
)

ndvi.styles(
    {
        "min": -1,
        "max": 1,
        "palette": ["#8c510a", "#f6e8c3", "#c7eae5", "#01665e"],
    }
).getMap(CONFIG["layer_name"])

oge.mapclient.centerMap(
    CONFIG["center_lon"],
    CONFIG["center_lat"],
    CONFIG["zoom"],
)
