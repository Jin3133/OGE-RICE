# 空间面积统计模块设计

## 目标

空间统计模块将候选区二值栅格、独立有效观测掩膜和管理单元边界转换为版本化`AreaStatistic`。本模块只负责面积，不识别水稻、不匹配灌溉定额，也不计算参考需水。

## 输入

- 候选区掩膜：单波段GeoTIFF，`1`为候选区、`0`为背景；
- 有效观测掩膜：单波段GeoTIFF，`1`为有效观测、`0`为未观测或质量不合格；
- 管理单元边界：显式声明CRS的GeoJSON；
- 管理单元、遥感结果及面积统计的版本信息。

候选区与有效观测掩膜必须具有相同CRS、仿射变换、宽度和高度。面积统计要求栅格使用具有明确线性单位的投影坐标系。

## 第一版统计口径

1. 边界像元采用像元中心落入法，即`all_touched=False`；
2. 只有同时位于边界内且有效观测掩膜为1的像元进入有效面积；
3. 候选面积只统计有效像元中的候选区，不把云区或未观测区当作背景；
4. 像元面积使用仿射变换行列式，并换算为平方米；
5. 边界内没有有效观测时拒绝生成面积记录；
6. 任一输入不对齐、非二值、缺失CRS或使用地理坐标系时直接报错，不隐式重采样。

## 输出

输出正式领域对象`AreaStatistic`，包含候选面积、有效观测面积、管理单元版本、遥感结果版本、统计方法、质量和自身版本。技术试验网格只用于测试空间算法，不作为正式管理单元写入业务层级。

## 运行入口

正式本地入口为`tools/run_spatial_statistics.py`，读取严格的JSON任务文件并输出一份`AreaStatistic` JSON。相对文件路径以任务JSON所在目录为基准解析，避免依赖启动命令所在目录或Mac绝对路径。

```bash
python tools/run_spatial_statistics.py \
  --job examples/spatial-statistics/v1/job.example.json \
  --output outputs/spatial-statistics/area-statistic.json
```

任务格式见`examples/spatial-statistics/v1/job.example.json`，对应Schema为`schemas/application/v1/spatial-statistics-job.schema.json`。其中示例路径只描述契约，运行前必须替换为实际文件。生成的面积记录可以直接加入领域仓储的`area_statistics`集合，再由`AssessmentService`匹配并计算参考需水。

## 已知边界

- 第一版不做亚像元面积比例统计；
- 第一版不自动融合多时相掩膜；
- 第一版不负责重投影或重采样，数据准备流程必须先完成对齐；
- 现有弱参考只能形成演示性统计结果，不能作为正式水稻面积。
