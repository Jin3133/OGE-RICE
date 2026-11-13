"""OGE Sentinel-2 裁剪与 NDVI 预处理链路试验。

当前固定六景属于 T50RKU，覆盖武汉南部江夏方向。这里使用一个明确标注为
试验范围的矩形验证流程，不将其冒充为江夏区行政边界。
"""

import oge


CONFIG = {
    "scene_id": "T50RKU_20251005T025529",
    "product_id": "S2_MSIL2A",
    "raster_crs": "EPSG:32650",
    "layer_name": "HGZ_JX_TRIAL_CLIP_NDVI_20251005",
    "map_center": (114.225, 30.25),
    "zoom": 11,
}

# WGS84 约为 114.10–114.35°E、30.15–30.35°N；下列坐标已转换到 UTM 50N。
# 正式运行时应替换为经核验并投影到 EPSG:32650 的行政区/灌区边界。
TRIAL_POLYGON_UTM50N = [[[
    [220663.79, 3338959.31],
    [244753.47, 3338372.83],
    [245270.50, 3360547.05],
    [221229.74, 3361135.85],
    [220663.79, 3338959.31],
]]]


oge.initialize()
service = oge.Service()

image = service.getCoverage(
    coverageID=CONFIG["scene_id"],
    productID=CONFIG["product_id"],
)

trial_geometry = service.getProcess("Geometry.MultiPolygon").execute(
    coordinates=TRIAL_POLYGON_UTM50N,
    crs=CONFIG["raster_crs"],
    geodesic="false",
)

clipped = service.getProcess("Coverage.clip").execute(image, trial_geometry)
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
