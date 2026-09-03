"""Fund market-session status endpoint used by the Fund Watch detail view."""
from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Query

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

app = FastAPI(title="Fund Watch Fund Status", version="1.0.0")
TZ = ZoneInfo("Asia/Shanghai")

DEMO = {
    "000961": {"fund_code": "000961", "fund_name": "天弘沪深300A", "latest_nav": 1.0234, "nav_date": None},
    "519674": {"fund_code": "519674", "fund_name": "银河创新成长混合", "latest_nav": 0.9842, "nav_date": None},
    "110022": {"fund_code": "110022", "fund_name": "易方达消费行业", "latest_nav": 1.1865, "nav_date": None},
}


def _fund(code: str) -> dict[str, Any] | None:
    url = __import__("os").getenv("DATABASE_URL")
    if url and psycopg is not None:
        try:
            with psycopg.connect(url, connect_timeout=3) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT fund_code,fund_name,nav,nav_date FROM fund_info WHERE fund_code=%s LIMIT 1", (code,))
                    row = cur.fetchone()
                    if row:
                        return {"fund_code": row[0], "fund_name": row[1], "latest_nav": float(row[2]) if row[2] is not None else None, "nav_date": row[3].isoformat() if row[3] else None}
        except Exception:
            pass
    return DEMO.get(code)


def _phase(now: datetime) -> tuple[str, str]:
    if now.weekday() >= 5:
        return "weekend", "休市 · 等待下个交易日"
    t = now.time()
    if t < time(9, 30):
        return "pre_open", "开盘前 · 暂无盘中估值"
    if time(9, 30) <= t <= time(11, 30) or time(13, 0) <= t <= time(15, 0):
        return "intraday", "盘中 · 当前为估算净值"
    if t > time(15, 0):
        return "post_close", "收盘后 · 等待官方净值披露"
    return "lunch_break", "午间休市 · 下午开盘后继续估值"


@app.get("/api/fund-status")
def fund_status(fund_code: str = Query(..., min_length=6, max_length=6)) -> dict[str, Any]:
    fund = _fund(fund_code)
    if not fund:
        return {"code": 404, "data": {"fund_code": fund_code, "banner": "基金不存在"}}
    now = datetime.now(TZ)
    phase, banner = _phase(now)
    official_nav = fund.get("latest_nav")
    nav_date = fund.get("nav_date")
    is_today = bool(nav_date and nav_date[:10] == now.date().isoformat())
    is_final = phase == "post_close" and is_today
    return {
        "code": 0,
        "data": {
            "fund_code": fund_code,
            "fund_name": fund.get("fund_name"),
            "market_phase": phase,
            "banner": "今日官方净值已定稿" if is_final else banner,
            "official_nav": official_nav,
            "official_nav_date": nav_date,
            "official_status": "final" if is_final else ("published" if official_nav is not None else "unavailable"),
            "is_final": is_final,
            "timezone": "Asia/Shanghai",
            "as_of": now.isoformat(),
        },
    }
