# OGE 平台验证记录

## 武汉一号数据目录与影像读取

- 数据产品：武汉一号全色多光谱融合数据；
- OGE 产品编号：`LJ3II_L1B_Fusion`；
- 目录数量：1071 景；
- 时间范围：2024 年 6 月至 2026 年 6 月；
- 分辨率与级别：0.5 米，L1B；
- 测试影像：`LJ3II_FUS_E114.13_N29.97_20240606_L1B_010`；
- 云量：0%；
- 波段：B1/BLUE、B2/GREEN、B3/RED，数据页产品介绍还说明包含近红外信息，
  但当前波段表中未展示 B4，需后续实测确认。

2026-10-15 平台实测：使用上述正式产品编号和影像编号后，
`getCoverage`、`Coverage.selectBands` 与地图图层显示均运行成功。

## `whu-cultivated_land` 模型

- 调用方式：`service.getProcess("whu-cultivated_land").execute(image)`
- 目标：生成武汉一号融合影像的耕地候选区。
- 2026-10-15 最终复测：使用 `LJ3II_L1B_Fusion` 与数据中心实际影像编号后，
  模型运行成功并生成 `Cultivated_Land_Candidate` 图层。
- 结论：先前 `ThirdSource` 的 GeoJSON 错误由无效或不匹配的产品参数触发，
  不是该模型本身不可用。

## 无效参数的历史对照测试

为排除耕地模型自身或输入影像不匹配，使用同一景 `LJ3II_PAN_MSS` 影像调用
`whu01_water` 水体提取模型。2026-10-15 实测仍返回同类错误：

`算子 [ThirdSource] 内部错误: 创建文件异常 .../whu01_water-output-....geojson (No such file or directory)`

后续核对数据中心后确认，`LJ3II_PAN_MSS` 不是该融合数据在当前目录中的
正式产品编号。因此该组错误仅作为“产品参数必须以数据中心为准”的
排错记录，不再用于判定 `ThirdSource` 模型环境故障。

## 普通栅格算子对照测试

2026-10-15 使用 `Coverage.selectBands` 进行单波段读取对照测试：

- 旧测试影像 `LJ3II_HRF_E92.17_N37.01_20240721_0_L1A` 返回
  `DBQueryRestImpl: 未查询到元数据`；
- 换用耕地模型脚本中的
  `LJ3II_MSS_E114.07_N30.36_20241221_L1A_010_GS` 后，仍在影像读取阶段
  返回相同元数据错误，未进入 `Coverage.selectBands` 计算。

上述两次均使用了已失效或与当前数据目录不匹配的影像参数。换用
`LJ3II_L1B_Fusion` 和有效影像编号后，普通栅格流程与耕地模型均成功，
因此不应将该历史错误解读为平台侧服务故障。

## 当前开发决策

1. 使用 `LJ3II_L1B_Fusion` 和数据中心返回的实际影像编号；
2. 保留 `whu-cultivated_land` 作为 OGE 耕地候选区主线基线；
3. 开源模型仅作备选。`semanticricefield` 的仓库权重不完整，不能直接部署；
   `TerraSegNet` 有可用权重，但训练数据与武汉一号输入域不同，需要做输入和样本
   适配；
4. 下一步在武汉范围内选取包含连片农田的影像，评估耕地候选区成果质量，
   再串联水稻细化、面积统计和需水计算。
