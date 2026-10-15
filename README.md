# 禾灌智析（OGE Rice）

基于 OGE 平台的水稻种植监测与分阶段参考灌溉需水评估系统。

## 当前开发主线

1. 在 OGE 开发中心完成武汉一号影像读取、耕地候选区提取和面积统计脚本。
2. 将调试通过的 OGE 脚本发布为个人算法服务。
3. 由业务后台调用 OGE 服务，并完成分阶段参考灌溉需水计算。
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
