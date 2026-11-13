# Sentinel-2 耕地候选区弱标签实验记录

## 目标口径

本实验不区分水稻、小麦等作物类型。模型目标为提取已知水稻种植管理范围内的耕地候选区；“水稻”属性由任务区域及业务配置提供，而不是由当前影像模型独立判定。

## 数据组成

- 影像：江夏区 4 个 5 km 网格、每个网格 5 个 2025 年 Sentinel-2 时相，共 20 景。
- 输入波段：B02、B03、B04，空间分辨率 10 m。
- 标签：Microsoft Planetary Computer `io-lulc-annual-v02` 2023 年 Crops 类，作为公开弱参考。
- 空间划分：R03C06、R05C04 用于训练，R10C10 用于验证，R07C05 用于测试。
- 注意：同一网格的不同日期只进入一个集合，避免空间泄漏。

## 已完成实验

### 直接迁移

将高分辨率赛道三模型直接用于 Sentinel-2 后，不同日期的预测面积波动显著，并出现水体误识别。该权重不能作为可用成果直接部署。

### 旧权重弱标签微调

使用 10 景影像微调旧 DeepLabV3+ 权重。训练区拟合提升，但默认阈值 0.5 下跨网格泛化较弱。阈值扫描表明当前模型存在明显的概率校准偏差：

- 验证网格：阈值 0.10 时，与弱参考的 IoU 约为 0.396。
- 测试网格：阈值 0.10 时，与弱参考的 IoU 约为 0.378。

这些指标仅表示与 2023 年公开弱参考的一致程度，不是 2025 年地面真值精度，也不是水稻识别精度。

### ImageNet 初始化对照

使用同一训练集从 ImageNet 编码器初始化训练，在默认阈值 0.5 下验证集输出塌缩为背景。当前小样本条件下，它没有优于旧权重微调方案。

## 当前结论

当前链路已经证明数据读取、空间对齐、训练、验证和阈值分析均可运行，但模型尚不具备正式上线条件。下一步应优先增加目标区域的人工核验样本，并将多时相特征作为联合输入，而不是继续堆叠更复杂的模型名称。

## 关键文件

- 数据清单：`data/splits/sentinel_cropland_weak_v1.json`
- 统计量：`data/statistics/sentinel_cropland_weak_v1.json`
- 训练配置：`configs/deeplabv3plus_sentinel_weak.yaml`
- 当前最佳弱标签模型：`outputs/deeplabv3plus_sentinel_weak_v1/best.pt`
- 验证阈值报告：`outputs/deeplabv3plus_sentinel_weak_v1/validation_thresholds.json`
- 测试阈值报告：`outputs/deeplabv3plus_sentinel_weak_v1/test_thresholds.json`

