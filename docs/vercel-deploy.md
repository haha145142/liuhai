# Fund Watch · Vercel 部署方案

## 目标架构

- 前端：根目录静态 HTML + Vue 3 CDN，由 Vercel CDN 托管
- 主后端：`api/index.py`，FastAPI Python Function
- Cron：`api/cron/estimate.py`、`api/cron/calibrate.py`，均使用 `CRON_SECRET` 保护
- 数据库：PostgreSQL（推荐 Neon），连接串使用 `DATABASE_URL`
- 盘中刷新：前端每 30 秒轮询 `/api/funds/{fund_code}/estimate`；不依赖常驻进程

Vercel 官方提供 FastAPI 的 Python runtime；本项目使用 `api/` 文件型入口，`api/index.py` 暴露名为 `app` 的 FastAPI 实例。函数可在 `vercel.json` 中单独设置 `maxDuration` 和排除文件。

## 数据库策略

P0 代码支持两种模式：

1. 未配置 `DATABASE_URL`：使用明确标记的 `demo` 数据，网站仍可打开。
2. 配置 `DATABASE_URL`：读取 PostgreSQL 中的基金、净值、持仓和自选数据。

初始化脚本：`sql/init.postgres.sql`

Serverless 环境不要依赖本地 SQLite 文件持久化。生产环境建议使用数据库提供方的 pooled/连接池端点，降低并发连接压力。

## 环境变量

```text
DATABASE_URL=postgresql://<pooled-user>:<password>@<host>/<database>?sslmode=require
CRON_SECRET=<随机长字符串>
AKSHARE_TOKEN=<可选>
TUSHARE_API_KEY=<可选>
```

示例文件：`.env.example`。

绝不把真实密码、API token 或 `.env` 文件提交到 GitHub。

## Cron 策略

Cron 路由已经单独建立：

```text
GET /api/cron/estimate
GET /api/cron/calibrate
```

两个路由都校验：`Authorization: Bearer <CRON_SECRET>`。

当前 `vercel.json` 暂不写入具体 `crons` 计划，避免在尚未配置 `CRON_SECRET` 或尚未确认套餐频率策略时产生无意义的失败任务。后续只需往 `vercel.json` 增加 `crons` 数组即可启用。

盘中高频估值仍以浏览器轮询为基础，因此不会依赖 Vercel Cron 频率。

## 依赖控制

当前运行依赖保持精简：

- FastAPI
- psycopg[binary]

暂不加入 pandas、numpy、scikit-learn、akshare 等重量依赖。估值引擎需要矩阵计算时，再按实际测试结果最小化引入，避免无谓扩大 Serverless bundle。

## 数据采集边界

Vercel Function 适合短请求和无状态计算，不适合常驻 `while True` 采集器。因此行情采集器应设计为：

`外部数据源 → 标准化/缓存 → 估值 API`

后续需要长期保存历史行情、官方净值和估值快照时，再通过 PostgreSQL/Neon 持久化。

## 当前状态

- GitHub：`haha145142/liuhai`
- Vercel：已可部署
- FastAPI：已进入 Vercel Python Function
- PostgreSQL：代码已准备，`DATABASE_URL` 尚未配置时仍可用 Demo 模式
- 真实实时行情采集器：下一开发阶段接入
