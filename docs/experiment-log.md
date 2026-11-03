# 平台试验记录

## 2026-11-03：固定六景与单景 NDVI

- OGE 脚本位置：`我的资源 / 代码脚本 / rice-s2-stage-collection.py.py`；
- 固定集合：六景 `S2_MSIL2A`，场景编号见
  `data/catalog/sentinel2_fixed_six.txt`；
- 试验场景：`T50RKU_20250816T025529`；
- 试验算子：`Coverage.normalizedDifference`；
- 输入波段：`B08`、`B04`；
- 输出图层：`S2_Jiangxia_NDVI_20250816`；
- 平台结果：运行成功，地图图层正常加载；
- 说明：当前试验验证的是数据读取、波段运算与地图发布链路，尚未完成云掩膜、
  示范区精确裁剪和水稻分类。
