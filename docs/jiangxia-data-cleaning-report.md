# 江夏区 Sentinel-2 数据清洗交付说明

## 清洗结果

本轮形成了可复现的江夏区时序遥感数据底座。原始 Sentinel-2 影像不重复下载，继续由
OGE 数据中心托管并通过产品编号和场景编号在线调用；本地仓库保存边界、分析网格、
质量状态和处理任务清单。

六景候选影像清洗后分为三档：

- 核心时序 4 景：2025-05-11、2025-07-05、2025-08-16、2025-10-05；
- 补充时序 1 景：2025-05-01，已验证读取，作为移栽前后背景；
- 条件时序 1 景：2025-07-24，NDVI 已运行，但目录云量缺失，暂不进入默认任务清单。

核心时序覆盖水稻移栽前后、分蘖至拔节、抽穗前后和灌浆成熟期。场景质量与用途详见
`data/catalog/sentinel2_inventory.csv`。

## 空间清洗结果

公开江夏区边界已统一至 EPSG:32650，并切分为 107 个与江夏区相交的 5 km 网格，
其中核心网格 83 个、边缘网格 24 个。网格清单记录范围、中心坐标、区内覆盖率和角色。

已在 OGE 实跑 `JX5K_R07C05` 的 2025-10-05 场景，完成裁剪、B08/B04 NDVI 计算
及地图发布，验证小网格处理链路可用。

## 数据实际存放位置

### OGE 平台

- Sentinel-2 原始影像：OGE 数据中心产品 `S2_MSIL2A`；
- 江夏区投影边界：`myData/jiangxia_420115_utm50n.geojson`；
- 已验证预览脚本：`我的资源 / 代码脚本 / rice-jiangxia-tiny01-ndvi.py.py`；
- 已验证导出脚本：`我的资源 / 代码脚本 / rice-jiangxia-r07c05-ndvi-export.py.py`；
- 已验证临时图层：`HGZ_JIANGXIA_TINY01_NDVI_20251005`；
- 持久化 GeoTIFF：`我的资源 / 批处理结果 / HGZ_JX5K_R07C05_NDVI_20251005.tif.tif`。

地图图层属于 On-the-fly 会话结果，不应视为长期数据文件。`JX5K_R07C05` 的
2025-10-05 NDVI 已按 EPSG:32650、10 m/px、TIF 格式进入 OGE“批处理结果”，
可以直接复用，无需再次裁剪。平台会自动追加扩展名，本次界面输入已带 `.tif`，因此
实际文件名出现 `.tif.tif`；后续任务的输出文件名不再手动填写扩展名。

### 本地仓库

- 边界：`data/boundaries/jiangxia_420115_utm50n.geojson`；
- 5 km 网格：`data/grids/jiangxia_5km_grid_utm50n.geojson`；
- 网格属性：`data/catalog/jiangxia_5km_grid.csv`；
- 影像质量清单：`data/catalog/sentinel2_inventory.csv`；
- 场景—网格任务表：`data/catalog/jiangxia_s2_processing_tasks.csv`；
- OGE 同步脚本：`oge_scripts/14_jiangxia_tile01_ndvi.py`；
- 可复现生成脚本：`scripts/build_jiangxia_grid_catalog.py`。

本地不保存 Sentinel-2 原始大幅影像，因此仓库中的“数据包”是可复现的资源索引和处理
配置，而不是影像副本。

## 当前完成边界

本轮已完成数据发现、场景分级、坐标统一、空间网格化、任务编目及单网格链路验证。
已从完整任务池中选择 3 个空间样区和 5 个关键时相，完成 15 张 NDVI GeoTIFF 的
持久化输出，均保存在 OGE“我的资源/批处理结果”。算法数据包索引见
`data/catalog/jiangxia_algorithm_dataset.csv`。其余全区任务尚未批量输出；尚未进行
云掩膜和水稻分类。
这些属于后续批处理与算法阶段，不能与本轮基础数据清洗混称为已经完成。
