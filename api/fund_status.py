"""Fund session status and official-NAV reconciliation endpoint."""
from __future__ import annotations

import os
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

from core.live_data import fetch_fund_valuations

app = FastAPI(title="Fund Watch Fund Status", version="1.0.0")
CST = ZoneInfo("Asia/Shanghai")


def _db_fund(code: str) -> dict[str, Any] | None:
    url = os.getenv("DATABASE_URL")
    if not url or psycopg is None:
        return None
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT fund_code,fund_name,fund_type,nav,nav_date,is_index FROM fund_info WHERE fund_code=%s LIMIT 1",
                    (code,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "fund_code": row[0], "fund_name": row[1], "fund_type": row[2],
                    "nav": float(row[3]) if row[3] is not None else None,
                    "nav_date": row[4], "is_index": bool(row[5]),
                }
    except Exception:
        return None


def _phase(now: datetime) -> str:
    if now.weekday() >= 5:
        return "closed"
    t = now.time()
    if time(9, 30) <= t < time(11, 30) or time(13, 0) <= t < time(15, 0):
        return "intraday"
    if t >= time(15, 0):
        return "post_close"
    return "pre_open"


def _phase_label(phase: str) -> str:
    return {
        "pre_open": "未开盘",
        "intraday": "盘中",
        "post_close": "收盘后",
        "closed": "休市",
    }.get(phase, phase)


def _status_for(
    fund_code: str,
    latest_nav: float | None,
    estimated_nav: float | None,
    source: str,
    provider_status: str | None,
) -> dict[str, Any]:
    now = datetime.now(CST)
    phase = _phase(now)
    fund = _db_fund(fund_code)
    demo_nav = {"000961": 1.0234, "519674": 0.9842, "110022": 1.1865}.get(fund_code)
    official_nav = (fund or {}).get("nav") if fund else demo_nav
    nav_date = (fund or {}).get("nav_date") if fund else None
    if isinstance(nav_date, datetime):
        nav_date = nav_date.date()

    official_today = bool(nav_date and nav_date == now.date())
    is_final = phase == "post_close" and official_today and source not in {"demo", "demo-no-intraday"}
    gap = None
    if official_nav and estimated_nav is not None:
        gap = (estimated_nav / official_nav - 1) * 100

    if source in {"demo", "demo-no-intraday"} or provider_status == "unavailable":
        official_status = "demo"
    elif is_final:
        official_status = "official-final"
    elif phase in {"intraday", "pre_open"}:
        official_status = "latest-official"
    else:
        official_status = "pending-official"

    if is_final:
        banner = "今日官方净值已定稿"
    elif phase == "post_close":
        banner = "收盘后：等待今日官方净值披露"
    elif phase == "intraday":
        banner = "盘中：当前值为估算净值，收盘后以官方净值为准"
    elif phase == "closed":
        banner = "休市：展示最近一次官方净值"
    else:
        banner = "开盘前：展示最近一次官方净值"

    return {
        "fund_code": fund_code,
        "market_phase": phase,
        "market_phase_label": _phase_label(phase),
        "official_nav": official_nav,
        "official_nav_date": nav_date.isoformat() if nav_date else None,
        "official_status": official_status,
        "is_final": is_final,
        "estimated_nav": estimated_nav,
        "estimate_vs_official_pct": round(gap, 4) if gap is not None else None,
        "latest_nav": latest_nav,
        "banner": banner,
        "source": source or "unknown",
        "provider_status": provider_status,
        "checked_at": now.isoformat(),
    }


@app.get("/api/fund-status")
def fund_status(fund_code: str = Query(..., min_length=6, max_length=6)) -> dict[str, Any]:
    fund = _db_fund(fund_code)
    try:
        live = fetch_fund_valuations([fund_code]).get(fund_code, {})
    except Exception as exc:
        live = {"provider_error": str(exc)}

    if not fund and not live and fund_code not in {"000961", "519674", "110022"}:
        raise HTTPException(status_code=404, detail="基金不存在")

    latest_nav = live.get("latest_nav") or ((fund or {}).get("nav"))
    estimated_nav = live.get("estimated_nav")
    source = live.get("source") or ("postgres" if fund else "demo")
    return {"code": 0, "data": _status_for(fund_code, latest_nav, estimated_nav, source, live.get("provider_status"))}
