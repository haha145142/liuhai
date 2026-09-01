# Fund Watch · Vercel 部署方案

## 架构

- 前端：根目录静态 HTML + Vue 3 CDN，直接由 Vercel 静态托管
- 后端：`api/index.py`，FastAPI Python Function
- 数据库：Neon / PostgreSQL，连接串使用 `DATABASE_URL`
- 盘中刷新：前端每 30 秒轮询估值 API（Hobby 基线）
- 盘后校准：预留 `/api/cron/calibrate`，由 `CRON_SECRET` 保护

Vercel 当前支持 FastAPI 通过 Python runtime 直接部署；`api/index.py` 暴露名为 `app` 的 FastAPI 实例即可被识别。

## 环境变量

```text
DATABASE_URL=postgresql://<pooled-user>:<password>@<host>/<database>?sslmode=require
CRON_SECRET=<随机长字符串>
```

不要把数据库密码、API token 或 `.env` 文件提交到 GitHub。

## 数据库

执行：

```text
sql/init.postgres.sql
```

生产环境建议使用 Neon 的连接池端点，避免 Serverless 并发请求创建过多数据库连接。

## Hobby 基线

本项目的 `vercel.json` **不配置高频 Cron**，避免 Hobby 计划因 Cron 频率限制而无法部署。盘中估值由浏览器轮询 `/api/funds/{fund_code}/estimate` 完成。

未来升级到支持所需频率的计划后，可以将：

```text
/api/cron/estimate
/api/cron/calibrate
```

接入 Vercel Cron，并在路由中校验 `Authorization: Bearer <CRON_SECRET>`。

## 当前数据模式

没有配置 `DATABASE_URL` 时，API 会使用明确标注为 `demo` 的演示数据，保证首页可以正常打开；这不是实时市场行情。

配置 PostgreSQL 后，基金基础信息、净值、持仓和自选读取会优先使用数据库数据。实时股票行情采集器仍需下一阶段接入正式数据源。
