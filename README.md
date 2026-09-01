# Fund Watch

新一代基金看盘软件 P0（MVP）。项目已针对 Vercel Serverless 架构完成第一轮改造。

## P0 核心模块

- 实时估值看板
- 自选基金分组
- 持仓透视
- 市场指数与行业雷达

## Vercel 架构

```text
浏览器
  ↓
Vercel Static Frontend
  ↓ same-origin /api
Vercel Python Function · FastAPI
  ↓
Neon PostgreSQL（DATABASE_URL）
```

盘中 Hobby 基线采用浏览器 30 秒轮询估值 API；高频 Cron 留待升级到支持所需频率的 Vercel 计划后开启。

## 本地/生产数据说明

未配置 `DATABASE_URL` 时，页面会使用明确标记为 `demo` 的演示数据，便于 UI 与 API 联调；它不是实时行情。

配置 Neon PostgreSQL 后，基金信息、净值、持仓和自选列表会优先从数据库读取。正式实时股票/指数行情采集器属于下一阶段数据源接入工作。

## 目录

```text
api/index.py             # Vercel FastAPI 入口
index.html               # P0 Web 入口
app.js                   # Vue 3 CDN 前端逻辑
styles.css               # Liquid Glass 风格
sql/init.postgres.sql    # Neon/PostgreSQL 初始化
backend/                 # 原 P0 后端工程，供后续算法层继续演进
docs/vercel-deploy.md    # Vercel 部署与环境变量说明
```

## 下一步

1. 创建 Neon 数据库并设置 `DATABASE_URL`。
2. 初始化 `sql/init.postgres.sql`。
3. 接入正式基金净值、持仓和实时行情数据源。
4. 将原有估值引擎接到 Vercel API，建立“估算 → 官方净值 → 精度校验”闭环。
