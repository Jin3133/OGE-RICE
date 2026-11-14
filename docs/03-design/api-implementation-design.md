# FastAPI实现设计与开源项目取舍

## 调研对象

### [FastAPI官方全栈模板](https://github.com/fastapi/full-stack-fastapi-template)

参考其应用入口、版本前缀、路由聚合、依赖注入和稳定OpenAPI operation ID设计。项目不照搬其用户、邮件、前端和SQLModel示例，只保留与本项目相关的HTTP组织方式。

### [stac-fastapi](https://github.com/stac-utils/stac-fastapi)

参考其API核心与具体后端实现分离的思想。禾灌智析同样保持领域/应用服务不依赖FastAPI，使OGE、本地算法和未来Provider可以替换，HTTP层只做协议适配。

### [Zalando RESTful API Guidelines](https://github.com/zalando/restful-api-guidelines)

采用API-first、OpenAPI稳定性、统一错误表达和创建操作幂等原则。幂等记录必须与业务写入保持事务一致，不能只在进程内缓存一个Key。

### [Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines)

采用请求标识、乐观并发和长任务状态资源模式。遥感与空间统计预计超过普通HTTP等待时间，因此后续以异步任务资源返回状态地址，不使用FastAPI进程内后台任务承担可靠计算。

## 本项目第一版结构

```text
oge_main/
  domain/       纯领域对象与规则
  application/  用例、仓储协议与空间统计
  api/          FastAPI适配层
    routes/     按业务资源拆分的版本化路由
```

HTTP路由不得直接实现面积或需水公式；路由通过依赖注入取得应用服务。Pydantic领域模型仍是业务契约来源，HTTP专有的错误、健康检查和任务状态另设模型。

## 暂不引入的内容

- 暂不复制完整微服务或DDD目录模板；
- 暂不实现虚假的内存持久化业务API；
- 暂不使用FastAPI `BackgroundTasks`运行需要恢复、重试和审计的遥感任务；
- 暂不开放宽泛CORS、鉴权占位逻辑或没有真实需求的CRUD；
- PostgreSQL、Alembic和任务队列在持久化契约实现阶段引入。
