"""OGE 武汉一号耕地候选区提取基线。

将本文件内容复制到 OGE 开发中心的代码脚本中运行。脚本调通后可按平台规范
发布为个人算法服务。输出是耕地候选区，不应直接表述为水稻识别结果。
"""

import oge


oge.initialize()
service = oge.Service.initialize()

# OGE 会读取此参数块，为发布服务生成输入表单。
""" begin param definition
Args:
  coverageID (String): 武汉一号融合影像的唯一标识
  productID (String): 武汉一号产品类型编码
end param definition """

# 开发中心直接运行时使用的测试影像。发布服务后由调用方传入。
coverageID = "LJ3II_FUS_E114.13_N29.97_20240606_L1B_010"
productID = "LJ3II_L1B_Fusion"

image = service.getCoverage(
    coverageID=coverageID,
    productID=productID,
)

# OGE 已有模型：适用于武汉一号融合数据的耕地提取模型。
cultivated_land = service.getProcess("whu-cultivated_land").execute(image)

# 平台预览。服务化时以 Coverage 成果作为后续面积统计或水稻细化的输入。
cultivated_land.styles(["#000000", "#39A96B"]).getMap(
    "Cultivated_Land_Candidate"
)
oge.mapclient.centerMap(114.1376, 29.9834, 12)
