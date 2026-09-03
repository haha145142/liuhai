"""Fund Watch FastAPI entrypoint for Vercel.

The app is stateless. PostgreSQL is optional infrastructure: when
DATABASE_URL is configured, persistent reads come from PostgreSQL. Without it,
the UI remains usable with clearly labelled fallback data. Intraday estimates
use the current TianTian Fund H5 valuation adapter when available.
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

from core.live_data import fetch_fund_valuations

app = FastAPI(title="Fund Watch API", version="0.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEMO_FUNDS = [
    {"fund_code": "000961", "fund_name": "天弘沪深300A", "fund_type": "指数型", "nav": 1.0234, "estimated_nav": 1.0311, "change_pct": 0.75, "confidence": "高"},
    {"fund_code": "519674", "fund_name": "银河创新成长混合", "fund_type": "混合型", "nav": 0.9842, "estimated_nav": 0.9937, "change_pct": 0.96, "confidence": "中"},
    {"fund_code": "110022", "fund_name": "易方达消费行业", "fund_type": "股票型", "nav": 1.1865, "estimated_nav": 1.1789, "change_pct": -0.64, "confidence": "中"},
]

DEMO_HOLDINGS = {
    "000961": [("600519", "贵州茅台", 5.5, 1.2), ("601318", "中国平安", 3.5, 0.7), ("600036", "招商银行", 3.0, 0.4), ("000858", "五粮液", 2.5, 1.1), ("000333", "美的集团", 2.0, 0.9)],
    "519674": [("688981", "中芯国际", 8.5, 2.8), ("688111", "金山办公", 6.5, 1.6), ("688012", "中微公司", 5.5, 2.2), ("688036", "传音控股", 4.5, 1.0), ("688008", "澜起科技", 4.0, 1.8)],
    "110022": [("600519", "贵州茅台", 9.5, 1.2), ("000858", "五粮液", 7.5, 1.1), ("600887", "伊利股份", 5.5, 0.4), ("000568", "泸州老窖", 5.0, -0.3), ("600690", "海尔智家", 4.0, 0.8)],
}

DEMO_INDUSTRY_ALLOCATION = {
    "000961": [("食品饮料", 28.0), ("银行", 17.0), ("非银金融", 12.0), ("家用电器", 10.0), ("其他", 33.0)],
    "519674": [("电子", 34.0), ("计算机", 26.0), ("通信", 11.0), ("机械设备", 8.0), ("其他", 21.0)],
    "110022": [("食品饮料", 42.0), ("家用电器", 12.0), ("医药生物", 10.0), ("商贸零售", 7.0), ("其他", 29.0)],
}

DEMO_INDICES = [
    {"code": "000001", "name": "上证指数", "price": 3850.2, "change_pct": 0.82},
    {"code": "000300", "name": "沪深300", "price": 4522.1, "change_pct": 0.95},
    {"code": "000905", "name": "中证500", "price": 6844.5, "change_pct": 1.26},
    {"code": "399006", "name": "创业板指", "price": 2780.8, "change_pct": 1.81},
    {"code": "HSI", "name": "恒生指数", "price": 25840.3, "change_pct": -0.32},
    {"code": "IXIC", "name": "纳斯达克", "price": 21540.2, "change_pct": 0.44},
]

DEMO_INDUSTRIES = [
    {"code": "sw27", "name": "电子", "change_pct": 2.72, "leading_stock": "中芯国际"},
    {"code": "sw28", "name": "计算机", "change_pct": 2.15, "leading_stock": "金山办公"},
    {"code": "sw06", "name": "家用电器", "change_pct": 1.34, "leading_stock": "美的集团"},
    {"code": "sw01", "name": "食品饮料", "change_pct": 0.92, "leading_stock": "贵州茅台"},
    {"code": "sw20", "name": "医药生物", "change_pct": 0.31, "leading_stock": "恒瑞医药"},
    {"code": "sw14", "name": "房地产", "change_pct": -0.74, "leading_stock": "万科A"},
]

DEMO_ALERTS = [
    {"id": 1, "type": "异动", "title": "自选基金单日波动阈值", "detail": "超过 ±3% 时提醒", "enabled": True},
    {"id": 2, "type": "连跌", "title": "连续3天下跌", "detail": "基金净值连续三日收跌时提醒", "enabled": True},
    {"id": 3, "type": "公告", "title": "基金经理变更", "detail": "监测基金公司公告", "enabled": True},
    {"id": 4, "type": "限额", "title": "申购限额变化", "detail": "限购/放开/暂停时提醒", "enabled": True},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_rows(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    url = os.getenv("DATABASE_URL")
    if not url or psycopg is None:
        return []
    with psycopg.connect(url, connect_timeout=3) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description is None:
                return []
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _db_fund(code: str) -> dict[str, Any] | None:
    rows = _db_rows(
        "SELECT fund_code,fund_name,fund_type,nav,nav_date,is_index FROM fund_info WHERE fund_code=%s LIMIT 1",
        (code,),
    )
    return rows[0] if rows else None


def _fallback_fund(code: str) -> dict[str, Any] | None:
    return next((x for x in DEMO_FUNDS if x["fund_code"] == code), None)


def _demo_nav_history(code: str, points: int = 48) -> list[dict[str, Any]]:
    fund = _fallback_fund(code)
    if not fund:
        return []
    base = float(fund["nav"])
    slope = float(fund.get("change_pct", 0)) / 100 / max(points - 1, 1)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    out: list[dict[str, Any]] = []
    for i in range(points):
        wave = math.sin(i / 4.2) * 0.0014 + math.sin(i / 9.0) * 0.0007
        nav = base * (1 + slope * i + wave)
        out.append({"time": (now - timedelta(minutes=(points - 1 - i) * 30)).isoformat(), "nav": round(nav, 6)})
    return out


def _xirr_monthly(payments: list[float], final_value: float, months: int) -> float | None:
    if months <= 0 or final_value <= 0 or not payments:
        return None
    cashflows = [-float(p) for p in payments] + [float(final_value)]
    dates = list(range(len(payments))) + [months]

    def npv(rate: float) -> float:
        return sum(cf / ((1 + rate) ** (m / 12)) for cf, m in zip(cashflows, dates))

    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        value = npv(mid)
        if abs(value) < 1e-10:
            return mid
        if npv(lo) * value <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


@app.get("/api")
def root() -> dict[str, Any]:
    return {"name": "Fund Watch", "version": "0.4.0", "status": "ok", "mode": "postgres" if os.getenv("DATABASE_URL") else "demo"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    db_ok = False
    if os.getenv("DATABASE_URL") and psycopg is not None:
        try:
            _db_rows("SELECT 1")
            db_ok = True
        except Exception:
            db_ok = False
    return {
        "code": 0,
        "status": "healthy",
        "mode": "postgres" if os.getenv("DATABASE_URL") else "demo",
        "database": "ok" if db_ok else ("not_configured" if not os.getenv("DATABASE_URL") else "error"),
        "time": _now(),
    }


@app.get("/api/funds")
def funds() -> dict[str, Any]:
    rows = _db_rows("SELECT fund_code,fund_name,fund_type,nav,nav_date,is_index FROM fund_info ORDER BY fund_code LIMIT 200")
    if rows:
        for r in rows:
            r["nav"] = float(r["nav"]) if r["nav"] is not None else None
            r["source"] = "postgres"
            r["confidence"] = "高" if r.get("is_index") else "中"
        try:
            live = fetch_fund_valuations([r["fund_code"] for r in rows])
        except Exception:
            live = {}
        for r in rows:
            r.update(live.get(r["fund_code"], {}))
        return {"code": 0, "data": rows, "source": "postgres"}

    try:
        live = fetch_fund_valuations([x["fund_code"] for x in DEMO_FUNDS])
    except Exception:
        live = {}
    data = []
    for item in DEMO_FUNDS:
        merged = {**item, **live.get(item["fund_code"], {})}
        merged["source"] = merged.get("source") or "demo"
        if merged.get("provider_status") == "unavailable":
            merged["source"] = "demo-no-intraday"
        data.append(merged)
    return {"code": 0, "data": data, "source": "live-provider-or-demo"}


@app.get("/api/funds/{fund_code}/estimate")
def estimate(fund_code: str) -> dict[str, Any]:
    fund = _db_fund(fund_code)
    try:
        live = fetch_fund_valuations([fund_code]).get(fund_code, {})
    except Exception as exc:
        live = {"provider_error": str(exc)}

    if fund:
        nav = float(fund["nav"] or 0)
        if live.get("estimated_nav") is not None:
            return {"code": 0, "data": {
                "fund_code": fund_code,
                "fund_name": fund["fund_name"],
                "fund_type": fund["fund_type"],
                "latest_nav": live.get("latest_nav") or nav,
                "estimated_nav": live["estimated_nav"],
                "estimated_change_pct": live.get("estimated_change_pct"),
                "valuation_time": live.get("valuation_time"),
                "confidence": "数据源实时估值",
                "source": live.get("source"),
                "snapshot_time": _now(),
            }}
        return {"code": 0, "data": {
            "fund_code": fund_code, "fund_name": fund["fund_name"], "fund_type": fund["fund_type"],
            "latest_nav": nav, "estimated_nav": None, "estimated_change_pct": None,
            "confidence": "暂无盘中估值", "source": "postgres", "snapshot_time": _now(),
        }}

    fallback = _fallback_fund(fund_code)
    if live and (live.get("estimated_nav") is not None or live.get("latest_nav") is not None):
        base = {**(fallback or {}), **live, "source": live.get("source", "live-provider")}
        return {"code": 0, "data": {**base, "snapshot_time": _now()}}
    if fallback:
        return {"code": 0, "data": {**fallback, "source": "demo", "snapshot_time": _now()}}
    raise HTTPException(status_code=404, detail="基金不存在")


@app.get("/api/funds/{fund_code}/nav-history")
def nav_history(fund_code: str, points: int = Query(default=48, ge=12, le=240)) -> dict[str, Any]:
    rows = _db_rows(
        "SELECT nav_date,nav FROM fund_nav_history WHERE fund_code=%s ORDER BY nav_date DESC LIMIT %s",
        (fund_code, points),
    )
    if rows:
        rows.reverse()
        data = [{"time": r["nav_date"].isoformat(), "nav": float(r["nav"])} for r in rows]
        return {"code": 0, "data": data, "source": "postgres"}
    fallback = _fallback_fund(fund_code)
    if not fallback:
        raise HTTPException(status_code=404, detail="基金不存在")
    return {"code": 0, "data": _demo_nav_history(fund_code, points), "source": "demo"}


@app.get("/api/funds/{fund_code}/holdings")
def holdings(fund_code: str) -> dict[str, Any]:
    rows = _db_rows(
        "SELECT stock_code,stock_name,weight,is_top_ten,report_date FROM fund_holding WHERE fund_code=%s ORDER BY report_date DESC,weight DESC LIMIT 20",
        (fund_code,),
    )
    if rows:
        for r in rows:
            r["weight"] = float(r["weight"])
            r["is_top_ten"] = bool(r["is_top_ten"])
            if r["report_date"] is not None:
                r["report_date"] = r["report_date"].isoformat()
        return {"code": 0, "data": rows, "source": "postgres"}
    fallback = _fallback_fund(fund_code)
    data = [{"stock_code": c, "stock_name": n, "weight": w, "is_top_ten": True, "current_change_pct": chg} for c, n, w, chg in DEMO_HOLDINGS.get(fund_code, [])]
    if not data and not fallback:
        raise HTTPException(status_code=404, detail="基金不存在")
    return {"code": 0, "data": data, "source": "demo"}


@app.get("/api/funds/{fund_code}/industry-allocation")
def industry_allocation(fund_code: str) -> dict[str, Any]:
    rows = _db_rows(
        "SELECT industry_name,weight FROM fund_industry_alloc WHERE fund_code=%s ORDER BY weight DESC",
        (fund_code,),
    )
    if rows:
        return {"code": 0, "data": [{"industry_name": r["industry_name"], "weight": float(r["weight"])} for r in rows], "source": "postgres"}
    data = [{"industry_name": n, "weight": w} for n, w in DEMO_INDUSTRY_ALLOCATION.get(fund_code, [])]
    if not data and not _fallback_fund(fund_code):
        raise HTTPException(status_code=404, detail="基金不存在")
    return {"code": 0, "data": data, "source": "demo"}


@app.get("/api/funds/{fund_code}/contribution")
def contribution(fund_code: str) -> dict[str, Any]:
    data = holdings(fund_code)["data"]
    groups: dict[str, float] = {}
    for h in data:
        industry = "核心持仓"
        if h["stock_code"] in {"688981", "688111", "688012", "688008"}:
            industry = "电子/科技"
        elif h["stock_code"] in {"600519", "000858", "600887", "000568"}:
            industry = "食品饮料"
        groups[industry] = groups.get(industry, 0.0) + float(h.get("weight", 0)) * float(h.get("current_change_pct", 0) or 0) / 100
    items = [{"industry_name": k, "contribution": round(v, 4)} for k, v in sorted(groups.items(), key=lambda x: x[1], reverse=True)]
    return {"code": 0, "data": {"fund_code": fund_code, "industries": items}}


@app.get("/api/market/indices")
def indices() -> dict[str, Any]:
    return {"code": 0, "data": DEMO_INDICES, "source": "demo"}


@app.get("/api/market/industries")
def industries() -> dict[str, Any]:
    return {"code": 0, "data": DEMO_INDUSTRIES, "source": "demo"}


@app.get("/api/market/erp")
def erp() -> dict[str, Any]:
    # Demo indicator only; real ERP needs synchronized valuation + bond yield sources.
    return {"code": 0, "data": {"erp_pct": 3.42, "percentile": 63, "label": "中性偏低估", "source": "demo"}}


@app.get("/api/alerts")
def alerts() -> dict[str, Any]:
    return {"code": 0, "data": DEMO_ALERTS, "source": "demo"}


@app.get("/api/watchlist/groups")
def watchlist_groups() -> dict[str, Any]:
    rows = _db_rows("SELECT id,group_name,sort_order FROM watchlist_group WHERE user_id=1 ORDER BY sort_order,id")
    if rows:
        return {"code": 0, "data": [{"id": r["id"], "name": r["group_name"]} for r in rows], "source": "postgres"}
    return {"code": 0, "data": [{"id": 1, "name": "我的自选"}, {"id": 2, "name": "定投组合"}, {"id": 3, "name": "观察清单"}], "source": "demo"}


@app.get("/api/watchlist/{group_id}")
def watchlist(group_id: int) -> dict[str, Any]:
    rows = _db_rows("SELECT fund_code FROM watchlist_item WHERE group_id=%s ORDER BY sort_order,id", (group_id,))
    codes = [r["fund_code"] for r in rows] if rows else [x["fund_code"] for x in DEMO_FUNDS]
    data = []
    for c in codes:
        try:
            data.append(estimate(c)["data"])
        except HTTPException:
            continue
    avg = sum(float(x.get("estimated_change_pct") or x.get("change_pct") or 0) for x in data) / len(data) if data else 0
    return {"code": 0, "data": data, "summary": {"fund_count": len(data), "avg_change_pct": round(avg, 4)}}


@app.get("/api/backtest/dca")
def dca_backtest(
    start_nav: float = Query(default=1.0, gt=0),
    monthly_amount: float = Query(default=1000.0, gt=0),
    months: int = Query(default=36, ge=3, le=240),
    annual_return: float = Query(default=0.08, ge=-0.99, le=5.0),
    frequency: str = Query(default="monthly"),
) -> dict[str, Any]:
    normalized = frequency.lower()
    periods = months if normalized == "monthly" else (months * 2 if normalized == "biweekly" else months * 4)
    contribution_per_period = monthly_amount if normalized == "monthly" else monthly_amount / (2 if normalized == "biweekly" else 4)
    period_return = (1 + annual_return) ** (1 / 12) - 1
    if normalized == "biweekly":
        period_return = (1 + annual_return) ** (1 / 24) - 1
    elif normalized == "weekly":
        period_return = (1 + annual_return) ** (1 / 48) - 1
    nav = start_nav
    shares = 0.0
    invested = 0.0
    series = []
    for i in range(periods):
        nav *= 1 + period_return
        shares += contribution_per_period / nav
        invested += contribution_per_period
        if i % max(1, periods // 12) == 0 or i == periods - 1:
            value = shares * nav
            series.append({"period": i + 1, "nav": round(nav, 6), "value": round(value, 2), "invested": round(invested, 2)})
    final_value = shares * nav
    irr = _xirr_monthly([contribution_per_period] * periods, final_value, months if normalized == "monthly" else int(months * (2 if normalized == "biweekly" else 1)))
    return {"code": 0, "data": {
        "frequency": normalized,
        "months": months,
        "total_invested": round(invested, 2),
        "final_value": round(final_value, 2),
        "profit": round(final_value - invested, 2),
        "irr_pct": round((irr or 0) * 100, 2),
        "series": series,
        "model": "mock geometric return; replace with actual historical NAV for production backtest",
    }}


@app.get("/api/cron/calibrate")
def cron_calibrate(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    secret = os.getenv("CRON_SECRET")
    if not secret or authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"code": 0, "success": True, "message": "Calibration hook ready; official NAV collector remains to be wired.", "time": _now()}
