"""Cron hook for batch estimation.

This route is intentionally safe to deploy before a paid/high-frequency Cron
plan is enabled. It only reports the current data mode until the live quote
collector is connected.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from core.cron_security import authorized
from core.database import configured, fetch_all

app = FastAPI(title="Fund Watch estimate cron")


@app.get("/")
def run(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not configured():
        return {
            "code": 0,
            "success": True,
            "mode": "demo",
            "estimated": 0,
            "message": "DATABASE_URL not configured; no batch writes performed.",
            "time": datetime.now(timezone.utc).isoformat(),
        }

    funds = fetch_all("SELECT fund_code FROM fund_info WHERE status=1 ORDER BY fund_code LIMIT 500")
    return {
        "code": 0,
        "success": True,
        "mode": "postgres",
        "fund_count": len(funds),
        "message": "Estimate batch hook ready; live quote collector is the next stage.",
        "time": datetime.now(timezone.utc).isoformat(),
    }
