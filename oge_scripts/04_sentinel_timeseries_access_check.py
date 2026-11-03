"""验证武汉 T50RKU 关键时相 Sentinel-2 场景是否可在 OGE 读取。"""

import oge


oge.initialize()
service = oge.Service.initialize()

scene_ids = [
    "T50RKU_20250705T030601",
    "T50RKU_20250816T025529",
    "T50RKU_20251005T025529",
]

for index, scene_id in enumerate(scene_ids):
    coverage = service.getCoverage(
        coverageID=scene_id,
        productID="S2_MSIL2A",
    )
    red = service.getProcess("Coverage.selectBands").execute(coverage, ["B04"])
    red.styles({"min": -100, "max": 100}).getMap(f"S2_T50RKU_{index + 1}")

oge.mapclient.centerMap(114.3, 30.5, 10)
