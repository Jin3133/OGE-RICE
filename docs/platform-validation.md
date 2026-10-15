# OGE 平台验证记录

## 武汉一号影像读取

- 测试产品：`LJ3II_PAN_MSS`
- 测试影像：`LJ3II_MSS_E114.07_N30.36_20241221_L1A_010_GS`
- 影像读取及地图定位可执行。

## `whu-cultivated_land` 模型

- 调用方式：`service.getProcess("whu-cultivated_land").execute(image)`
- 目标：生成武汉一号融合影像的耕地候选区。
- 2026-10-15 平台实测：模型在服务端创建输出 GeoJSON 时失败。
- 平台返回：`算子 [ThirdSource] 内部错误: 创建文件异常 .../whu-cultivated_land-output-....geojson (No such file or directory)`。

该错误发生于 OGE 服务端任务目录，不是本地业务后台或需水计算造成。后续处理顺序：

1. 核对模型详情页中的输入产品和示例代码；
2. 使用官方示例影像复测；
3. 若错误稳定复现，保留脚本并等待平台侧修复；
4. 同时开发基于可用波段和样本的轻量水稻识别备用流程，避免阻塞整体业务闭环。

## 武汉一号模型对照测试

为排除耕地模型自身或输入影像不匹配，使用同一景 `LJ3II_PAN_MSS` 影像调用
`whu01_water` 水体提取模型。2026-10-15 实测仍返回同类错误：

`算子 [ThirdSource] 内部错误: 创建文件异常 .../whu01_water-output-....geojson (No such file or directory)`

两种不同模型均在各自的 GeoJSON 输出阶段失败，说明问题更可能位于 OGE
`ThirdSource` 模型运行环境或服务端任务目录，而不是某一个模型、影像编号或
可视化样式。当前云端脚本已恢复为耕地候选区主线版本。
