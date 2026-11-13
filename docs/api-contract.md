# 历史纵向验证接口约定

> 本文档对应早期最小业务闭环验证，保留用于理解演进过程。正式领域接口以 `schemas/domain/v1`、`examples/domain/v1` 和 `docs/03-design/business-domain-design.md` 为准；新代码不得继续依赖本文中的临时任务结构和关注等级规则。

## 业务边界

当前遥感模型输出统一称为“耕地候选区”。任务中的 `crop_type=rice` 来自已知的水稻种植管理范围或管理人员配置，不代表模型完成了水稻与其他作物的分类。

参考灌溉需水量采用 `W=A×M`：面积 `A` 以亩参与计算，分阶段灌溉定额 `M` 的单位为立方米/亩，结果 `W` 为立方米。结果不等同于实际取水量、供水量或灌溉用水量。

## 任务输入

任务至少包含任务编号、业务范围、作物类型、生育阶段、阶段定额、质量说明和管理单元。每个管理单元提供候选区栅格；人工核查后可通过 `area_override_m2` 覆盖栅格面积。

完整示例见：

- `examples/business-cycle/demo-task-v1.json`
- `examples/business-cycle/demo-task-v2-feedback.json`

## 结果输出

输出包含：

- 任务和成果版本；
- 各管理单元候选面积（平方米、亩）；
- 分阶段参考灌溉需水量；
- 任务内需水占比及高、中、低关注等级；
- 遥感栅格来源、坐标系和像元大小；
- 质量说明、反馈记录和适用限制。

首版关注等级为任务内部相对等级：需水占比不低于 35% 为高，20% 至 35% 为中，其余为低。该规则仅用于演示，后续应替换为灌区确认的业务规则。

## 版本更新

用户修正面积或参数后，新任务保留同一 `task_id`，递增 `result_version`，并填写 `parent_result_version` 和 `feedback`。系统重新计算全部受影响指标，同时保留旧版本结果。

## 当前调用方式

```bash
.venv/bin/python tools/run_business_cycle.py \
  examples/business-cycle/demo-task-v1.json \
  --output outputs/business-cycle/jiangxia-demo-2025-tillering/v1/result.json
```

后续 Web 后台只需将同一输入输出结构封装为 HTTP API；业务计算本身无需改写。
