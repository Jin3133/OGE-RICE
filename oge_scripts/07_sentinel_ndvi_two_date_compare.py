"""对比水稻种植季前期与中后期 Sentinel-2 NDVI。"""

import oge


oge.initialize()
service = oge.Service()

early = service.getCoverage(
    coverageID="T50RKU_20250501T030529",
    productID="S2_MSIL2A",
)
mid_late = service.getCoverage(
    coverageID="T50RKU_20250816T025529",
    productID="S2_MSIL2A",
)

early_ndvi = service.getProcess("Coverage.normalizedDifference").execute(
    early,
    ["B08", "B04"],
)
mid_late_ndvi = service.getProcess("Coverage.normalizedDifference").execute(
    mid_late,
    ["B08", "B04"],
)

ndvi_style = {
    "min": -1,
    "max": 1,
    "palette": ["#8c510a", "#f6e8c3", "#c7eae5", "#01665e"],
}

early_ndvi.styles(ndvi_style).getMap("S2_NDVI_20250501")
mid_late_ndvi.styles(ndvi_style).getMap("S2_NDVI_20250816")
oge.mapclient.centerMap(114.2, 30.25, 11)
