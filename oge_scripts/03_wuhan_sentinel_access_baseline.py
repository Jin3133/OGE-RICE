"""OGE 当前账号可运行的武汉区域 Sentinel-2 读取基线。"""

import oge


oge.initialize()
service = oge.Service.initialize()

coverage_id = "T50RKU_20250501T030529"
product_id = "S2_MSIL2A"

coverage = service.getCoverage(
    coverageID=coverage_id,
    productID=product_id,
)

red = service.getProcess("Coverage.selectBands").execute(coverage, ["B04"])
red.styles({"min": -100, "max": 100}).getMap("Wuhan_Sentinel_Access")
oge.mapclient.centerMap(114.3, 30.5, 10)
