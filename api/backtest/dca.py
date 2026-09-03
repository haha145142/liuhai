"""Historical-NAV DCA backtest endpoint for Fund Watch.

This function is intentionally separate from api/index.py so the stable FastAPI
entrypoint is not modified. When PostgreSQL has enough fund_nav_history data,
the calculation uses actual historical NAVs. Without a database, it returns a
clearly-labelled demo model instead of pretending that historical data exists.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None

app = FastAPI(title="Fund Watch DCA Backtest", version="1.0.0")


def _rows(fund_code: str) -> list[dict[str, Any]]:
    url = os.getenv("DATABASE_URL")
    if not url or psycopg is None:
        return []
    sql = """
        SELECT nav_date, nav
        FROM fund_nav_history
        WHERE fund_code = %s
          AND nav IS NOT NULL
        ORDER BY nav_date ASC
    """
    try:
        with psycopg.connect(url, connect_timeout=4) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (fund_code,))
                return [{"date": r[0], "nav": float(r[1])} for r in cur.fetchall()]
    except Exception:
        return []


def _nearest(rows: list[dict[str, Any]], target: date) -> dict[str, Any] | None:
    if not rows:
        return None
    # Prefer the latest NAV on or before the requested contribution date.
    candidate = None
    for row in rows:
        d = row["date"].date() if isinstance(row["date"], datetime) else row["date"]
        if d <= target:
            candidate = row
        else:
            break
    return candidate or rows[0]


def _add_months(d: date, months: int) -> date:
    total = d.year * 12 + (d.month - 1) + months
    year, month0 = divmod(total, 12)
    month = month0 + 1
    day = min(d.day, monthrange(year, month)[1])
    return date(year, month, day)


def _xirr(cashflows: list[tuple[date, float]]) -> float | None:
    if len(cashflows) < 2:
        return None
    t0 = cashflows[0][0]

    def npv(rate: float) -> float:
        return sum(cf / ((1.0 + rate) ** ((d - t0).days / 365.0)) for d, cf in cashflows)

    lo, hi = -0.9999, 10.0
    flo, fhi = npv(lo), npv(hi)
    if flo == 0:
        return lo
    if flo * fhi > 0:
        # Expand upper bound for unusually large positive returns.
        for _ in range(8):
            hi *= 2
            fhi = npv(hi)
            if flo * fhi <= 0:
                break
        else:
            return None
    for _ in range(120):
        mid = (lo + hi) / 2
        fmid = npv(mid)
        if abs(fmid) < 1e-10:
            return mid
        if flo * fmid <= 0:
            hi, fhi = mid, fmid
        else:
            lo, flo = mid, fmid
    return (lo + hi) / 2


def _demo(start_nav: float, monthly_amount: float, months: int, frequency: str) -> dict[str, Any]:
    periods_per_month = {"monthly": 1, "biweekly": 2, "weekly": 4}[frequency]
    periods = months * periods_per_month
    # Neutral demonstration path: intentionally labelled as a model, not history.
    annual_return = 0.08
    period_return = (1 + annual_return) ** (1 / (12 * periods_per_month)) - 1
    nav = start_nav
    shares = 0.0
    invested = 0.0
    first = date.today()
    series: list[dict[str, Any]] = []
    for i in range(periods):
        nav *= 1 + period_return
        contribution = monthly_amount / periods_per_month
        shares += contribution / nav
        invested += contribution
        if i % max(1, periods // 12) == 0 or i == periods - 1:
            series.append({"period": i + 1, "nav": round(nav, 6), "value": round(shares * nav, 2), "invested": round(invested, 2)})
    final_value = shares * nav
    flows = [(first, -monthly_amount)]
    for i in range(1, periods):
        days = round(365 * i / (12 * periods_per_month))
        flows.append((first + timedelta(days=days), -(monthly_amount / periods_per_month)))
    flows.append((first + timedelta(days=round(365 * months / 12)), final_value))
    irr = _xirr(flows)
    return {
        "frequency": frequency,
        "months": months,
        "total_invested": round(invested + monthly_amount, 2),
        "final_value": round(final_value + monthly_amount, 2),
        "profit": round(final_value, 2),
        "irr_pct": round((irr or 0) * 100, 2),
        "series": series,
        "source": "demo-model",
        "data_quality": "demo; no historical NAV database configured",
    }


@app.get("/api/backtest/dca")
def dca_backtest(
    fund_code: str = Query(..., min_length=6, max_length=6),
    start_date: date | None = Query(default=None),
    monthly_amount: float = Query(default=1000.0, gt=0),
    months: int = Query(default=36, ge=3, le=240),
    frequency: str = Query(default="monthly"),
) -> dict[str, Any]:
    freq = frequency.lower().strip()
    if freq not in {"monthly", "biweekly", "weekly"}:
        raise HTTPException(status_code=400, detail="frequency must be monthly, biweekly, or weekly")

    rows = _rows(fund_code)
    if not rows:
        return {"code": 0, "data": _demo(start_nav=1.0, monthly_amount=monthly_amount, months=months, frequency=freq)}

    first_available = rows[0]["date"].date() if isinstance(rows[0]["date"], datetime) else rows[0]["date"]
    last_available = rows[-1]["date"].date() if isinstance(rows[-1]["date"], datetime) else rows[-1]["date"]
    start = start_date or _add_months(last_available, -months)
    if start < first_available:
        raise HTTPException(status_code=422, detail=f"历史数据不足：可用区间 {first_available} 至 {last_available}")
    end = _add_months(start, months)
    if end > last_available:
        end = last_available

    periods_per_month = {"monthly": 1, "biweekly": 2, "weekly": 4}[freq]
    step_days = {"monthly": None, "biweekly": 14, "weekly": 7}[freq]
    dates: list[date] = []
    if freq == "monthly":
        for i in range(months):
            dates.append(_add_months(start, i))
    else:
        d = start
        while d <= end:
            dates.append(d)
            d += timedelta(days=step_days)
    if not dates:
        raise HTTPException(status_code=422, detail="没有可用回测区间")

    per_period = monthly_amount / periods_per_month
    shares = 0.0
    invested = 0.0
    flows: list[tuple[date, float]] = []
    series: list[dict[str, Any]] = []
    first_nav = None
    for i, d in enumerate(dates):
        row = _nearest(rows, d)
        if row is None or row["nav"] <= 0:
            continue
        nav = float(row["nav"])
        if first_nav is None:
            first_nav = nav
        shares += per_period / nav
        invested += per_period
        used_date = row["date"].date() if isinstance(row["date"], datetime) else row["date"]
        flows.append((used_date, -per_period))
        value = shares * nav
        if i % max(1, len(dates) // 12) == 0 or i == len(dates) - 1:
            series.append({"period": i + 1, "date": used_date.isoformat(), "nav": round(nav, 6), "value": round(value, 2), "invested": round(invested, 2)})

    if not flows:
        raise HTTPException(status_code=422, detail="没有有效历史净值")
    final_date = flows[-1][0]
    final_nav_row = _nearest(rows, final_date)
    final_nav = float(final_nav_row["nav"]) if final_nav_row else first_nav or 1.0
    final_value = shares * final_nav
    flows.append((final_date, final_value))
    irr = _xirr(flows)
    profit = final_value - invested
    return {"code": 0, "data": {
        "fund_code": fund_code,
        "frequency": freq,
        "months": months,
        "start_date": start.isoformat(),
        "end_date": final_date.isoformat(),
        "total_invested": round(invested, 2),
        "final_value": round(final_value, 2),
        "profit": round(profit, 2),
        "return_pct": round(profit / invested * 100, 2) if invested else 0,
        "irr_pct": round((irr or 0) * 100, 2),
        "series": series,
        "source": "postgres-history",
        "data_quality": "historical NAV",
    }}
