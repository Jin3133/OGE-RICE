# 禾灌智析（OGE Rice）

基于 OGE 平台的水稻种植监测与分阶段参考灌溉需水评估系统。

项目采用双层工程结构：OGE 负责遥感数据资产、在线计算和服务发布，Git 仓库负责
源码、目录、参数、数据注册表和实验版本。详见 `docs/platform-resource-layout.md` 与
`oge_scripts/README.md`。

## 当前开发主线

1. 盘点 OGE 可稳定调用的高分辨率数据并确定示范区与核心数据集。
2. 运行平台水稻相关模型形成基线，再与团队已有模型开展对照。
3. 将验证通过的遥感流程发布为服务，由业务后台完成分阶段参考需水计算。
4. 使用 Web 地图展示水稻分布、面积、阶段需水和重点关注区域。

## 项目结构

```text
oge-rice/
├── oge_scripts/       # 粘贴到 OGE 开发中心运行的 Python 脚本
├── backend/           # FastAPI 业务服务
├── frontend/          # Vue 3 Web 应用（下一阶段接入官方模板）
├── tests/             # 后台业务规则测试
└── docs/              # 架构、调研和平台操作说明
```

当前基线优先复用 OGE 平台的 `whu-cultivated_land` 算法形成耕地候选区。该结果不直接等同于水稻分布，后续将通过水稻样本、物候特征或专用模型进行替换或细化。

## 本地启动后台

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 3000
```

接口文档启动后位于 `http://127.0.0.1:3000/docs`。

将 `.env.example` 复制为本地 `.env` 并填写 OGE 服务配置后，后台可以通过
`POST /api/v1/oge/cultivated-land` 调用发布后的个人算法服务。真实 Token 和
AppKey 不进入 Git 仓库。
