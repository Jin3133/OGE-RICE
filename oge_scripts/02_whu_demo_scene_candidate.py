"""武汉一号第一候选演示场景：耕地候选区试跑。

本脚本仅用于比较演示场景质量。输出是耕地候选区，不等同于水稻分布。
确认空间效果后，再决定是否替换主基线脚本中的默认影像。
"""

import oge


oge.initialize()
service = oge.Service.initialize()

coverageID = "LJ3II_FUS_E114.40_N30.29_20240607_L1B_006"
productID = "LJ3II_L1B_Fusion"

image = service.getCoverage(
    coverageID=coverageID,
    productID=productID,
)

cultivated_land = service.getProcess("whu-cultivated_land").execute(image)

cultivated_land.styles(["#000000", "#39A96B"]).getMap(
    "Candidate_E114_40_N30_29"
)
oge.mapclient.centerMap(114.40, 30.29, 12)
