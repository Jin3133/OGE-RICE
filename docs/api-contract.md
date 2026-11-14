# 禾灌智析业务API契约 v1

## 1. 文档状态

| 项目 | 内容 |
|---|---|
| 状态 | v1冻结候选版 |
| 更新日期 | 2026-11-15 |
| API前缀 | `/api/v1` |
| JSON Schema | `schemas/domain/v1/`、`schemas/application/v1/` |
| 当前结果模式 | 仅`illustrative` |

本文定义业务后台、OGE/遥感Provider和Web端之间的稳定边界。HTTP服务尚未实现，但实现时必须遵守本文、领域Schema和示例JSON；不得重新使用早期`examples/business-cycle`中的临时字段。

## 2. 业务边界

当前遥感目标固定为`cultivated_land_candidate`，即耕地候选区。当前没有可靠水稻归属依据，因此v1只允许`result_mode=illustrative`，其含义为“假定已配置范围内候选耕地用于种植水稻的演示性情景测算”。

参考灌溉需水采用`W_m3 = A_mu × M_m3_per_mu`。候选面积以平方米存储，按`1亩=2000/3平方米`换算为亩。结果不是实际取水量、供水量或实际灌溉用水量。

正式业务模式不属于v1。未来只有在水稻归属证据、有效观测面积、正式阶段定额和管理单元边界均可追溯后，才通过新契约版本开放。

## 3. 核心资源与版本规则

| 资源 | 稳定标识 | 版本字段 | 是否不可变 |
|---|---|---|---|
| 管理单元 | `unit_id` | `version.revision` | 是 |
| 遥感成果 | `result_id` | `version.revision` | 是 |
| 面积统计 | `statistic_id` | `version.revision` | 是 |
| 定额定义 | `quota_id` | `version.revision` | 是 |
| 定额分配 | `assignment_id` | `version.revision` | 是 |
| 分析任务 | `task_id` | `revision` | 是 |
| 评估结果 | `assessment_id` | 结果引用任务版本 | 是 |

业务对象发布后不原地修改。修正时创建新版本并保留`previous`、变更原因、人员和时间。`superseded`仅表示不再供新任务默认选择，不影响历史任务按明确版本读取。

## 4. 总体调用顺序

1. 登记或选择管理单元、遥感成果和阶段定额版本；
2. 提交空间统计任务；
3. 空间统计完成后取得明确的`AreaStatistic`版本；
4. 创建分析任务，显式引用管理单元、遥感成果、面积统计和定额分配版本；
5. 执行参考需水评估；
6. 查询并展示结果；
7. 用户提交反馈后创建受影响对象的新版本，再创建新任务版本和新评估结果。

分析任务不得只引用遥感成果后临时查询“最新面积”。每个管理单元必须显式锁定一份面积统计版本。

## 5. 通用HTTP约定

### 5.1 请求

- `Content-Type: application/json; charset=utf-8`；
- 创建和执行类请求必须携带`Idempotency-Key`；
- 时间使用带时区的ISO 8601格式；日期使用`YYYY-MM-DD`；
- 面积统一存储为平方米，水量统一存储为立方米；
- 未知字段一律拒绝，不静默忽略。

### 5.2 幂等性

相同调用方、相同`Idempotency-Key`和相同请求体必须返回同一资源；相同Key但请求体不同返回`409 IDEMPOTENCY_KEY_REUSED`。服务端至少保留幂等记录24小时。

### 5.3 错误结构

```json
{
  "error": {
    "code": "RESOURCE_VERSION_NOT_FOUND",
    "message": "area statistic version was not found",
    "field": "area_statistics[0]",
    "details": {"record_id": "area.example", "revision": 2},
    "request_id": "req_01"
  }
}
```

| HTTP状态 | 错误代码示例 | 含义 |
|---|---|---|
| 400 | `INVALID_JSON` | JSON无法解析 |
| 404 | `RESOURCE_VERSION_NOT_FOUND` | 指定对象或版本不存在 |
| 409 | `VERSION_CONFLICT`、`OVERLAPPING_UNITS` | 版本或业务冲突 |
| 422 | `CONTRACT_VALIDATION_FAILED` | 字段、单位或业务规则不满足 |
| 500 | `INTERNAL_ERROR` | 未分类服务端错误 |
| 502 | `PROVIDER_ERROR` | OGE或遥感Provider调用失败 |

## 6. 空间统计任务

### 6.1 创建任务

`POST /api/v1/spatial-statistic-jobs`

请求体遵循`schemas/application/v1/spatial-statistics-job.schema.json`，示例见`examples/spatial-statistics/v1/job.example.json`。输入必须包含候选区掩膜、独立有效观测掩膜、管理单元边界及全部版本元数据。

响应为`202 Accepted`：

```json
{
  "job_id": "spjob_01",
  "status": "queued",
  "submitted_at": "2026-11-15T09:00:00+08:00",
  "status_url": "/api/v1/spatial-statistic-jobs/spjob_01"
}
```

状态只允许`queued → running → succeeded`，失败时为`failed`。终态不可改写；重试生成新运行记录，同一幂等键只允许写入一份面积统计版本。

### 6.2 查询任务

`GET /api/v1/spatial-statistic-jobs/{job_id}`

成功时返回面积统计明确版本：

```json
{
  "job_id": "spjob_01",
  "status": "succeeded",
  "area_statistic": {
    "record_id": "area.jx.zone.01.rs.2025.tillering.v1",
    "revision": 1
  }
}
```

### 6.3 空间统计准入规则

- 候选掩膜和有效观测掩膜必须为单波段0/1栅格；
- 两者CRS、尺寸、分辨率及仿射变换必须一致；
- CRS必须为具有明确线性单位的投影坐标系；
- 边界像元采用像元中心落入法；
- 未观测像元不作为背景，也不进入候选面积；
- 边界内无有效观测时拒绝生成面积结果；
- v1不执行隐式重投影、重采样或多时相融合。

## 7. 分析任务

### 7.1 创建任务

`POST /api/v1/analysis-tasks`

请求体遵循`analysis-task-create.schema.json`。关键字段包括：

- `result_mode`：v1固定为`illustrative`；
- `management_units`：明确管理单元版本；
- `remote_sensing_result`：明确遥感成果版本；
- `area_statistics`：每个管理单元恰好一份明确面积统计版本；
- `irrigation_quota_assignments`：每个管理单元恰好一份明确分配版本；
- `growth_stage`：系统推荐后允许用户确认或修改，人工操作必须记录人员和时间。

服务端必须验证：

1. 所有引用版本真实存在；
2. 管理单元在分析期内有效；
3. 管理单元属于同一不重叠统计层级，不允许父子混选；
4. 遥感成果覆盖全部管理单元，观测期与分析期相交；
5. 面积统计的管理单元和遥感成果版本与任务完全一致；
6. 定额作物、阶段、适用单元和有效期与任务一致；
7. v1结果模式只能为`illustrative`。

响应为`201 Created`，返回完整`AnalysisTask`及资源地址。

### 7.2 获取任务

- `GET /api/v1/analysis-tasks/{task_id}/versions/{revision}`：按明确版本读取；
- `GET /api/v1/analysis-tasks/{task_id}/latest`：只供交互界面定位当前版本，不得用于历史复算。

## 8. 参考需水评估

### 8.1 执行评估

`POST /api/v1/analysis-tasks/{task_id}/versions/{revision}/assessments`

```json
{"assessment_id": "assessment.jx.2025.tillering.0001"}
```

服务端只读取任务锁定的明确版本，不解析“最新”或“当前active”记录。即使输入后来变为`superseded`，历史任务仍可按原版本复算。复算不得覆盖旧评估，应创建新的`assessment_id`并记录任务版本。

响应遵循`reference-demand-assessment.schema.json`。结果必须保留三项限制：候选区不独立识别水稻；参考需水不是实际取供水；当前结果为演示性情景测算。

### 8.2 查询评估

`GET /api/v1/assessments/{assessment_id}`

评估结果不可变。页面展示和导出必须同时展示任务版本、面积版本、定额版本、公式和限制说明。

## 9. 反馈与版本更新

`POST /api/v1/feedback`请求遵循`feedback-record.schema.json`。反馈本身不直接覆盖原记录，也不自动改变历史结果。

应用反馈时依次：创建受影响对象新版本；必要时重新空间统计；创建分析任务新版本并显式引用新输入；创建新评估；保留原任务、原评估和版本关系。

## 10. 持久化和事务契约

### 10.1 写入原则

- 业务版本记录只追加，不更新历史有效载荷；
- 同一业务标识和revision必须唯一；
- 创建新版本、标记旧版本为`superseded`及写审计记录必须位于同一事务；
- 文件资产先完成上传及SHA-256校验，再提交引用资产的数据库事务；
- 数据库失败不得留下可被业务查询使用的半成品记录。

### 10.2 并发控制

创建revision `n+1`时必须提交预期父版本`n`。若当前版本已经变化，返回`409 VERSION_CONFLICT`，不得自动覆盖或跳号。

### 10.3 删除

已被任务或结果引用的记录禁止物理删除。撤销使用`withdrawn`状态；底层文件清理必须经过引用计数和保留期检查。

## 11. Provider边界

业务后台只依赖遥感Provider的四项能力：提交分析任务、查询状态、获取候选掩膜及有效观测资产、获取稳定模型和数据版本。OGE脚本、本地模型或其他平台都应适配该接口。业务层不得依赖平台私有临时路径、页面会话图层或未经版本化的“最新结果”。

## 12. 契约来源与验证

- 领域模型：`src/oge_main/domain/models.py`；
- 空间统计任务：`src/oge_main/application/spatial_statistics.py`；
- 领域Schema：`schemas/domain/v1/`；
- 应用任务Schema：`schemas/application/v1/`；
- 正式示例：`examples/domain/v1/`；
- 空间任务示例：`examples/spatial-statistics/v1/`；
- 自动测试：`tests/test_domain_models.py`、`tests/test_assessment_service.py`、`tests/test_spatial_statistics.py`。

字段调整应先修改模型与测试，再重新导出Schema并更新本文。只修改前端或数据库字段、不更新契约视为接口漂移。
