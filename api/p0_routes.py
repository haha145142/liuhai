"""P0 product APIs layered on top of the core Fund Watch service.

These routes intentionally keep calculations deterministic in demo mode so the
frontend can exercise the complete product flow before production data wiring.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
from typing import Any

from fastapi import HTTPException
from api.index import app, DEMO_FUNDS, DEMO_HOLDINGS, DEMO_INDICES, DEMO_INDUSTRIES


def _fund(code: str) -> dict[str, Any]:
    for item in DEMO_FUNDS:
        if item["fund_code"] == code:
            return item
    raise HTTPException(404, "基金不存在")


def _series(code: str, points: int = 60) -> list[dict[str, Any]]:
    f = _fund(code)
    base = float(f.get("nav") or f.get("estimated_nav") or 1.0)
    change = float(f.get("change_pct") or 0.0) / 100.0
    start = datetime.combine(date.today(), datetime.min.time()).replace(hour=9, minute=30, tzinfo=timezone.utc)
    out = []
    for i in range(points):
        t = start + timedelta(minutes=int(330 * i / max(points - 1, 1)))
        noise = math.sin(i * 0.63) * 0.0007
        nav = base * (1 + change * i / max(points - 1, 1) + noise)
        out.append({"time": t.isoformat(), "estimated_nav": round(nav, 6)})
    return out


@app.get("/api/funds/{fund_code}/intraday")
def intraday(fund_code: str) -> dict[str, Any]:
    _fund(fund_code)
    return {"code": 0, "data": {"fund_code": fund_code, "points": _series(fund_code)}}


@app.get("/api/funds/{fund_code}/industry-allocation")
def industry_allocation(fund_code: str) -> dict[str, Any]:
    rows = DEMO_HOLDINGS.get(fund_code)
    if rows is None:
        _fund(fund_code)
    groups: dict[str, float] = {}
    for code, name, weight, change in rows:
        if code in {"600519", "000858", "600887", "000568"}:
            industry = "食品饮料"
        elif code in {"601318"}:
            industry = "非银金融"
        elif code in {"600036"}:
            industry = "银行"
        elif code in {"000333", "600690"}:
            industry = "家用电器"
        else:
            industry = "电子/科技"
        groups[industry] = groups.get(industry, 0) + float(weight)
    total = sum(groups.values()) or 1
    return {"code": 0, "data": [{"industry_name": k, "weight": round(v / total * 100, 2)} for k, v in sorted(groups.items(), key=lambda x: x[1], reverse=True)]}


@app.get("/api/market/erp")
def market_erp() -> dict[str, Any]:
    # Demo-only proxy value; production should calculate ERP from live earnings yield and bond yield.
    return {"code": 0, "data": {"erp_pct": 4.18, "equity_yield_pct": 7.93, "bond_yield_pct": 3.75, "label": "股债性价比偏有利于权益", "source": "demo"}}


@app.get("/api/alerts")
def alerts() -> dict[str, Any]:
    return {"code": 0, "data": [
        {"type": "move", "title": "连续2日上涨", "detail": "519674 银河创新成长混合 · 估算动能偏强", "level": "info"},
        {"type": "nav", "title": "估算与官方净值偏离", "detail": "110022 易方达消费行业 · 盘后自动校准", "level": "warning"},
        {"type": "announcement", "title": "基金公告监控已开启", "detail": "基金经理变更、限额开放/暂停进入提醒中心", "level": "normal"},
    ]}


@app.get("/api/funds/{fund_code}/official-gap")
def official_gap(fund_code: str) -> dict[str, Any]:
    f = _fund(fund_code)
    official = float(f.get("nav") or 0)
    estimated = float(f.get("estimated_nav") or official)
    gap = ((estimated - official) / official * 100) if official else 0
    return {"code": 0, "data": {"fund_code": fund_code, "official_nav": official, "estimated_nav": estimated, "gap_pct": round(gap, 4), "status": "待盘后校准"}}
