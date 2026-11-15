# PostgreSQL/PostGIS持久化层调研与设计建议

## 1. 调研目标

本轮调研用于确定禾灌智析业务后台的数据库、ORM、迁移、空间数据、版本追溯和测试策略。目标不是尽快生成一批表，而是保证后续API、历史复算、反馈修正和OGE任务接入建立在稳定的数据模型上。

## 2. 调研来源

### [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)

重点参考Session事务边界、乐观并发版本计数和版本化行示例。SQLAlchemy明确指出Session代表一个有状态事务，不能在并发线程或异步任务间共享；推荐通过上下文管理器明确事务范围。其官方版本化示例展示了以新INSERT代替原地UPDATE、保留旧版本的方式。

### [Alembic](https://alembic.sqlalchemy.org/)

重点参考约束命名规范和自动迁移。Alembic说明自动生成迁移必须人工审查，尤其是约束条件变化；所有主键、外键、唯一、检查和索引都应使用稳定命名规范。

### [PostgreSQL](https://www.postgresql.org/docs/current/)

重点参考组合唯一约束、部分唯一索引、事务隔离和并发冲突。默认`READ COMMITTED`适合普通请求；复杂版本创建通过显式行锁、唯一约束和预期父版本实现，不把全系统默认提升到`SERIALIZABLE`。

### [PostGIS](https://postgis.net/docs/)

重点参考几何有效性、GiST空间索引和空间谓词。PostGIS默认不会自动拒绝无效多边形，因此需要显式`ST_IsValid`检查。`ST_Intersects`等谓词可以自动利用GiST索引。

### [GeoAlchemy2](https://geoalchemy-2.readthedocs.io/)

GeoAlchemy2提供PostGIS Geometry类型、空间函数和Alembic辅助能力。空间列迁移需要启用其Alembic helpers，并仍需人工检查自动生成结果。

### [FastAPI官方模板](https://github.com/fastapi/full-stack-fastapi-template)

参考“每请求一个Session”、依赖注入和迁移目录组织。项目不采用SQLModel，避免领域Pydantic模型、ORM模型和数据库约束耦合在同一个类中。

### [stac-fastapi-sqlalchemy](https://github.com/stac-utils/stac-fastapi-sqlalchemy)

参考空间列、JSONB资产元数据和读写连接分离思路。其历史代码依赖较旧SQLAlchemy风格，本项目只采用结构思想，不复制实现。

### [OpenAgri Irrigation Management](https://github.com/agstack/OpenAgri-IrrigationManagement)

该项目证明FastAPI、SQLAlchemy和Alembic适用于农业灌溉服务，但其通用CRUD在方法内部直接commit、捕获数据库异常后返回`None`，并允许通用原地更新和删除，不符合本项目不可变版本、统一错误与事务编排要求，因此不采用其CRUD基类。

## 3. 技术选型结论

| 项目 | 选择 | 原因 |
|---|---|---|
| 数据库 | PostgreSQL 16及以上 + PostGIS | 支持事务、组合约束、部分索引、范围类型和空间查询 |
| ORM | SQLAlchemy 2.0 Typed Declarative | 显式映射、成熟事务能力，不与API模型耦合 |
| 驱动 | psycopg 3 | PostgreSQL官方生态主流驱动，支持现代SQLAlchemy |
| 迁移 | Alembic + GeoAlchemy2 helpers | 版本化DDL和空间列迁移 |
| Web访问方式 | 同步Session、同步路由 | 首期业务量有限，结构更简单；每请求一个Session，不跨线程共享 |
| 空间列 | `geometry(MultiPolygon, 4326)` | 用于管理边界展示、层级和重叠校验 |
| 栅格 | 文件/对象存储资产，不进PostGIS Raster | 原始影像和掩膜体量大，已有GeoTIFF和哈希资产契约 |
| 核心字段 | 规范化关系列 | 保证外键、唯一性、检索和审计 |
| JSONB | 输入快照、Provider元数据等非关系型内容 | 不用于替代核心关系或版本外键 |

## 4. 分层结构

```text
domain/          Pydantic领域对象和业务规则
application/     用例与仓储Protocol
infrastructure/
  database/
    base.py      SQLAlchemy Base与命名规范
    models.py    ORM持久化模型
    session.py   Engine与Session工厂
    repositories.py  仓储实现，不提交事务
  migrations/   Alembic迁移
api/             依赖注入、路由和错误映射
```

仓储只执行查询、添加和flush，不自行commit。事务由应用用例边界统一管理，使“写新版本、替代旧版本、写审计、写幂等结果”能够原子提交。

## 5. 版本化存储策略

### 5.1 基本规则

每类资源使用稳定业务编号和revision组成唯一版本键，例如：

```text
PRIMARY KEY (unit_id, revision)
UNIQUE (unit_id, revision)
```

发布后的业务载荷不原地修改。创建新版本时：

1. 锁定当前版本行或资源头记录；
2. 校验客户端提交的预期父revision；
3. 插入`revision + 1`的新行；
4. 将旧版本生命周期状态改为`superseded`；
5. 写入审计事件和幂等响应；
6. 在同一事务中提交。

旧版本载荷保持不变，唯一允许变化的是生命周期状态。任务引用始终保存完整组合外键，不使用“latest”引用。

### 5.2 revision并发分配（已冻结）

每个版本化业务对象在`resource_heads`中保存当前revision。创建新版本时使用`SELECT ... FOR UPDATE`锁定资源头，校验客户端提交的预期父revision，在锁内分配`current_revision + 1`，随后插入新版本、替代旧版本、更新资源头并写审计。上述操作在同一事务中完成。

`(resource_id, revision)`唯一约束作为最终并发保护。不使用全局数据库序列分配业务revision，因为不同业务对象需要分别从1递增。首次创建时由资源头主键、版本组合唯一约束和幂等记录共同保证只生成一个revision 1。

死锁、连接中断或可重试的序列化失败允许有限次数重试；预期父revision过期属于业务冲突，不自动重试，返回`409 VERSION_CONFLICT`。

### 5.3 不采用的方案

- 不采用一个通用`records`大表加任意JSONB承载全部领域对象；
- 不使用ORM事件自动把所有UPDATE魔法转换为INSERT，版本创建由显式应用服务完成；
- 不依赖SQLAlchemy`version_id_col`替代业务revision。前者用于检测并发陈旧UPDATE，后者是可查询、可引用的业务版本，两者含义不同；
- 不通过数据库触发器隐藏主要业务版本流程，避免应用行为难以测试和解释。

## 6. 建议表结构

### 6.1 空间资产与管理单元

#### `spatial_assets`

- `asset_id`作为不可变资产的唯一主键；文件内容变化时创建新`asset_id`，不覆盖原记录；
- `href`、`media_type`、`roles`；
- `crs`、`checksum_sha256`；
- 来源、创建时间和质量元数据。

#### `management_unit_versions`

- 组合主键：`unit_id + revision`；
- `name`、`unit_type`、`valid_period`；
- `root_unit_id/root_revision`、`parent_unit_id/parent_revision`组合外键；
- `boundary_asset_id/boundary_asset_revision`；
- `geometry(MultiPolygon,4326)`；
- 质量、版本链和生命周期字段。

空间约束：

- `CHECK (ST_IsValid(geom))`；
- `CHECK (NOT ST_IsEmpty(geom))`；
- GiST空间索引；
- 灌区根节点及父子层级仍由领域规则校验；数据库负责引用完整性。

不在写入时静默执行`ST_MakeValid`。无效边界应拒绝并返回原因，避免系统在未记录的情况下改变用户提交几何。

### 6.2 遥感与面积

#### `remote_sensing_result_versions`

- `result_id + revision`；
- 目标类型、观测期、模型名称和版本；
- 掩膜资产组合外键；
- Provider、数据源、运行标识和质量字段。

#### `remote_result_management_units`

- 遥感成果版本与管理单元业务编号的关联；
- 复合唯一约束避免重复覆盖声明。

#### `area_statistic_versions`

- `statistic_id + revision`；
- 管理单元组合外键；
- 遥感成果组合外键；
- 候选面积、有效观测面积、统计方法；
- 统计时间、质量和版本字段。

数据库检查：候选面积非负、有效面积大于零、候选面积不超过有效面积。可增加部分唯一索引，保证同一管理单元版本和遥感成果版本最多只有一条`active`面积记录；历史任务仍按显式ID和revision读取旧记录。

### 6.3 定额

#### `irrigation_quota_definition_versions`

- `quota_id + revision`；
- 作物、阶段、`value_m3_per_mu`；
- 来源、质量和版本字段。

#### `irrigation_quota_assignment_versions`

- `assignment_id + revision`；
- 管理单元组合外键；
- 定额定义组合外键；
- 有效日期范围；
- 冗余保存只读的`crop_code`和`stage_code`，用于数据库约束。

为防止同一单元、作物和阶段出现重叠有效定额，建议启用`btree_gist`并建立排除约束：业务键使用等号、日期范围使用`&&`。冗余字段必须由应用服务从定额定义复制并核验，不能由客户端任意提交。

### 6.4 任务与结果

#### `analysis_task_versions`

- `task_id + revision`；
- 名称、业务范围、`result_mode`、作物、分析期；
- 生育阶段选择快照；
- 遥感成果组合外键；
- 状态、人员、时间和版本链。

#### 任务引用表

- `analysis_task_management_units`；
- `analysis_task_area_statistics`；
- `analysis_task_quota_assignments`。

每张表都保存任务组合键和被引用资源组合键。面积引用应同时记录对应管理单元，建立唯一约束保证“一单元一面积、一单元一定额分配”。

#### `reference_demand_assessments`

- `assessment_id`主键；
- 任务组合外键、生成时间和公式；
- 汇总面积、亩数、参考需水和限制说明；
- 结果模式固定继承任务，不允许单独提升为正式。

#### `assessment_unit_results`

- `assessment_id + unit_id`；
- 完整输入版本引用和数值快照；
- 单元参考需水结果。

结果表只追加，不更新。历史复算创建新的`assessment_id`。

### 6.5 任务运行、反馈和审计

#### `operations`

- 长任务ID、类型、状态、提交者；
- 目标资源引用；
- 排队、开始、结束时间；
- 稳定错误代码和脱敏错误信息。

#### `operation_attempts`

- 每次执行尝试、worker标识、心跳、重试次数和日志定位；
- operation与attempt分开，避免重试覆盖历史运行信息。

#### `feedback_records`

- 对应当前领域`FeedbackRecord`；
- 反馈只记录建议，不直接修改目标对象。

#### `audit_events`

- 操作人、时间、请求ID、资源类型、业务编号、版本、动作和摘要；
- 不保存密钥、完整令牌或大体量请求文件。

#### `idempotency_records`

- 调用方、幂等键、请求哈希构成唯一键；
- 保存处理状态、响应状态码、资源定位和过期时间；
- 与业务写入在同一事务中完成；
- 相同键但请求哈希不同返回冲突。

## 7. 空间与层级校验

### 7.1 入库校验

- GeoJSON在应用层规范化为MultiPolygon和EPSG:4326；
- 原始边界文件仍作为不可变资产保存；
- PostGIS执行`ST_IsValid`、空几何和SRID检查；
- 不自动修复或简化原始边界。

### 7.2 任务单元重叠

第一版要求同一统计层级、内部不重叠。边界相接不算重叠，内部存在正面积交叠才拒绝。查询可先利用GiST索引筛选候选对，再使用内部相交关系或交集面积判断。具体容差必须在真实边界样本验证后固定，不能提前写死一个无依据数值。

### 7.3 栅格职责

PostGIS只负责管理边界和空间关系，不承担当前GeoTIFF候选掩膜的像元面积统计。栅格统计继续由已完成的Rasterio空间模块执行，结果以`AreaStatistic`入库。这避免在首期同时维护两套栅格计算实现。

## 8. 事务与并发策略

### 8.1 Session生命周期

- 每个HTTP请求或worker任务创建独立Session；
- Session不在请求、线程或任务之间共享；
- 仓储不commit；应用服务使用`with session.begin()`控制原子事务；
- 异常统一回滚并在API边界映射为稳定错误代码。

### 8.2 隔离级别

普通读写使用PostgreSQL默认`READ COMMITTED`。创建新版本时锁定资源当前版本或头记录，并通过唯一约束和预期父revision检测竞争。只有确有跨多行不变量且锁定方案不足时，才针对单个事务采用更高隔离级别，并实现序列化失败重试；不将全库默认设为`SERIALIZABLE`。

### 8.3 写入顺序

文件上传与数据库事务分为两个阶段：先写临时对象并计算哈希，再在事务中写资产及业务引用；事务成功后转为正式可见状态。失败的临时文件由清理任务回收，不能留下数据库引用不到或校验不完整的正式资产。

### 8.4 Worker事务边界（已冻结）

Worker以“一个管理单元的一次空间统计”为最小任务和事务边界。GeoTIFF读取、掩膜校验和面积计算在数据库事务外完成；计算成功后开启短事务，在同一事务中写入面积统计版本、审计、幂等结果并将operation标记成功。计算失败时单独记录该单元失败，不回滚其他管理单元已经完成的结果。

多管理单元任务由编排层拆分为多个单元级operation，汇总层等待必要单元全部完成。首期不提供“整批全部成功或全部回滚”的长数据库事务语义。

## 9. Alembic迁移策略

- 全部约束和索引使用稳定命名规范；
- 第一份迁移显式安装`postgis`和`btree_gist`扩展；
- 配置GeoAlchemy2 Alembic helpers；
- 自动生成迁移后必须人工审查类型、外键、检查约束、部分索引和空间索引；
- 生产环境只运行已提交迁移，不在应用启动时调用`create_all()`；
- 迁移在空数据库升级、上一版本升级和必要的降级路径上分别测试。

## 10. 测试策略

### 单元测试

继续使用现有内存仓储验证领域规则和应用服务，不依赖数据库。

### PostgreSQL集成测试

使用真实PostgreSQL/PostGIS容器，不用SQLite替代以下行为：

- 组合外键和部分唯一索引；
- 日期范围排除约束；
- PostGIS几何有效性和GiST空间查询；
- 并发创建版本和幂等写入；
- Alembic从零升级。

### API测试

通过FastAPI依赖覆盖注入测试Session和仓储，验证HTTP状态、统一错误、事务回滚和请求ID。API测试不直接绕过应用服务写ORM。

## 11. 分阶段实施建议

### 阶段一：数据库基础

引入SQLAlchemy、psycopg、GeoAlchemy2和Alembic；建立Base、命名规范、配置、Session工厂、PostGIS测试容器和第一份迁移。

### 阶段二：只读仓储

先映射管理单元、遥感结果、面积、定额和任务，完成领域对象与ORM对象之间的显式转换，实现按ID和revision读取，替换内存仓储但不开放写API。

### 阶段三：版本化写入

实现创建初版、创建新版本、父版本冲突、状态替代、审计和幂等事务；完成并发测试后再开放创建接口。

### 阶段四：长任务持久化

实现operation和attempt模型，再接入空间统计与OGE Provider worker。任务状态必须在数据库中恢复，不依赖FastAPI进程内存。

## 12. 本轮建议冻结的决定

1. 使用SQLAlchemy 2.0，不使用SQLModel合并领域与ORM模型；
2. 第一版使用同步Session，仓储不commit；
3. 核心业务资源使用独立版本表和组合外键；
4. 管理边界进入PostGIS，栅格只保存资产与统计结果；
5. 使用显式版本用例，不使用通用CRUD和魔法ORM版本事件；
6. 数据库集成测试必须运行在真实PostgreSQL/PostGIS上；
7. 先完成只读仓储，再实现版本化写入和HTTP创建接口。
