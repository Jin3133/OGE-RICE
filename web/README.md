# 禾灌智析 Web

Vue 3 + TypeScript + Vite 前端工程。开发服务将 `/api` 请求代理到本地 FastAPI `8000` 端口，页面不写死后端地址。

## Docker 开发

```bash
docker compose -f compose.web.yml up --build
```

Web：<http://localhost:5173>

FastAPI 需另行启动：

```bash
OGE_DATABASE_URL=postgresql+psycopg://oge:oge_dev_password@127.0.0.1:55432/oge_rice \
  .venv/bin/uvicorn oge_main.api.app:app --host 0.0.0.0 --port 8000
```

## 本地 Node.js

Node.js 22+ 环境可直接运行：

```bash
npm install
npm run dev
```
