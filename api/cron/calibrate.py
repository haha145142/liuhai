"""Cron hook for post-market NAV calibration."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from core.cron_security import authorized
from core.database import configured, fetch_all

app = FastAPI(title="Fund Watch calibration cron")


@app.get("/")
def run(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not configured():
        return {
            "code": 0,
            "success": True,
            "mode": "demo",
            "calibrated": 0,
            "message": "DATABASE_URL not configured; calibration skipped.",
            "time": datetime.now(timezone.utc).isoformat(),
        }

    funds = fetch_all("SELECT fund_code FROM fund_info WHERE status=1 ORDER BY fund_code LIMIT 500")
    return {
        "code": 0,
        "success": True,
        "mode": "postgres",
        "fund_count": len(funds),
        "message": "Calibration hook ready; official NAV collector is the next stage.",
        "time": datetime.now(timezone.utc).isoformat(),
    }
