# 数据底座

OGE 资源的权威目录为 `catalog/oge_asset_registry.csv`。其中同时登记平台原生影像和
持久化的 `myData/` 资源，避免项目依赖数据中心中的松散名单。

本目录只保存可公开提交、体积较小的数据清单和参数模板，不直接提交大幅遥感影像、
训练样本或含有内部业务信息的原始台账。

## 目录结构

- `catalog/`：OGE 数据产品与影像场景清单；
- `parameters/`：作物历、分阶段灌溉定额和气象数据配置模板；
- `boundaries/`：分析区边界说明与字段模板；
- `grids/`：用于平台分块处理的规则分析网格；
- `quality/`：清洗规则和质量检查结果。
- `data_gap_register.csv`：必需数据、当前状态、责任人和验收条件。

## 统一约定

- 空间坐标统一使用 WGS 84（EPSG:4326）登记；进入面积计算前投影至适合当地的
  等积或米制坐标系；
- 日期采用 `YYYY-MM-DD`，种植季采用四位年份；
- 面积内部统一存储为平方米，展示时转换为公顷或亩；
- 水量统一存储为立方米，灌溉定额统一为立方米每亩；
- 缺失值留空并填写 `quality_status`，不得用 0 代替缺失；
- 每条数据必须保留来源、版本、适用区域和有效时期。

## 当前数据策略

当前主线采用 OGE 中已验证可运行的 `S2_MSIL2A`，示范区为武汉市江夏区。武汉一号
因当前账号仍无稳定计算权限，不作为首版流程的必要输入。

Sentinel-2 场景优先选择同一 MGRS 瓦片，并按水稻关键生育阶段组织。场景进入
算法输入前，必须同时通过平台读取、分析区有效覆盖、云与云影、波段完整性检查。

当前固定六景集合的场景编号保存在 `catalog/sentinel2_fixed_six.txt`，完整元数据和
质量状态保存在 `catalog/sentinel2_inventory.csv`。原始影像由 OGE 数据中心托管，
仓库不重复保存大体积影像文件。

江夏区已生成 107 个 5 km 分析网格和 535 条默认处理任务，分别见
`catalog/jiangxia_5km_grid.csv` 与 `catalog/jiangxia_s2_processing_tasks.csv`。

提交目录变更前运行：

```bash
.venv/bin/python scripts/validate_data_catalog.py
```
