"""OGE 固定六景 Sentinel-2 数据集合。"""

import oge


oge.initialize()
service = oge.Service()

scene_ids = [
    "T50RKU_20250501T030529",
    "T50RKU_20250511T030529",
    "T50RKU_20250705T030601",
    "T50RKU_20250724T030201",
    "T50RKU_20250816T025529",
    "T50RKU_20251005T025529",
]

images = service.getCoverageCollection(
    productID="S2_MSIL2A",
    coverageIDList=scene_ids,
)
