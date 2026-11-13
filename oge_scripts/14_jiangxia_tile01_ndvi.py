"""江夏区分块裁剪试验：01 号试验网格 NDVI。

整区行政边界在 OGE 交互式运行中响应不稳定，因此先以固定网格验证
“影像读取—空间裁剪—指数计算—地图发布”链路。后续应将江夏区切分为
多个网格逐块运行，再按任务编号组织结果。
"""

import oge


CONFIG = {
    "scene_id": "T50RKU_20251005T025529",
    "product_id": "S2_MSIL2A",
    "raster_crs": "EPSG:32650",
    "layer_name": "HGZ_JIANGXIA_TINY01_NDVI_20251005",
    "map_center": (114.22, 30.20),
    "zoom": 13,
}

# 江夏方向 5 km × 5 km 试验网格，坐标系为 UTM 50N。
TILE_01_UTM50N = [[[
    [230000.0, 3345000.0],
    [235000.0, 3345000.0],
    [235000.0, 3350000.0],
    [230000.0, 3350000.0],
    [230000.0, 3345000.0],
]]]


oge.initialize()
service = oge.Service()

image = service.getCoverage(
    coverageID=CONFIG["scene_id"],
    productID=CONFIG["product_id"],
)

tile_geometry = service.getProcess("Geometry.MultiPolygon").execute(
    coordinates=TILE_01_UTM50N,
    crs=CONFIG["raster_crs"],
    geodesic="false",
)

clipped = service.getProcess("Coverage.clip").execute(image, tile_geometry)
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
).getMap(CONFIG["layer_name"])

oge.mapclient.centerMap(
    CONFIG["map_center"][0],
    CONFIG["map_center"][1],
    CONFIG["zoom"],
)
