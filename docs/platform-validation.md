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

