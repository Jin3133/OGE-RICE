"""在江夏候选小范围验证 Sentinel-2 裁剪、NDVI 与地图输出。"""

import oge


oge.initialize()
service = oge.Service()

image = service.getCoverage(
    coverageID="T50RKU_20250816T025529",
    productID="S2_MSIL2A",
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
).getMap("S2_Jiangxia_NDVI_20250816")

oge.mapclient.centerMap(114.2, 30.25, 11)
