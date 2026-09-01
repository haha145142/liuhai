"""Lightweight live market adapters for Vercel Serverless Functions.

The provider is intentionally dependency-light: stdlib urllib/json only.
It targets the current TianTian Fund H5 valuation endpoint rather than the
retired fundgz JSONP endpoint.
"""
from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

VALUATION_URLS = (
    "https://fundcomapi.tiantianfunds.com/mm/newCore/FundValuationLast",
    "https://fundcomapi.eastmoney.com/mm/newCore/FundValuationLast",
)
VALUATION_FIELDS = "FCODE,SHORTNAME,GSZZL,GZTIME,GSZ,NAV,PDATE"


def _get_json(url: str, params: dict[str, str], timeout: float = 5.0) -> Any:
    full = f"{url}?{urlencode(params)}"
    request = Request(
        full,
        headers={
            "User-Agent": "Mozilla/5.0 (Fund-Watch/0.1)",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://h5.1234567.com.cn/",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("Data", "data", "Result", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
            if isinstance(value, dict):
                for subkey in ("Data", "data", "Rows", "rows", "Items", "items"):
                    sub = value.get(subkey)
                    if isinstance(sub, list):
                        return [x for x in sub if isinstance(x, dict)]
    return []


def fetch_fund_valuations(codes: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch current intraday estimates in one batched request.

    Values are returned as provider-native numbers plus normalized aliases.
    A provider returning null GSZ is preserved as unavailable instead of
    being converted into a fake 0.0 estimate.
    """
    normalized = sorted({str(c).strip() for c in codes if str(c).strip()})
    if not normalized:
        return {}

    params = {
        "FCODES": ",".join(normalized),
        "FIELDS": VALUATION_FIELDS,
        "_": str(int(time.time() * 1000)),
    }
    payload = None
    last_error: Exception | None = None
    for endpoint in VALUATION_URLS:
        try:
            payload = _get_json(endpoint, params)
            if payload is not None:
                break
        except Exception as exc:  # upstream failures are isolated
            last_error = exc

    if payload is None:
        raise RuntimeError(f"Fund valuation provider unavailable: {last_error}")

    result: dict[str, dict[str, Any]] = {}
    for row in _rows(payload):
        code = str(row.get("FCODE") or row.get("fundcode") or row.get("FCode") or "").strip()
        if not code:
            continue
        gsz = row.get("GSZ", row.get("gsz"))
        gszzl = row.get("GSZZL", row.get("gszzl"))
        nav = row.get("NAV", row.get("dwjz"))
        result[code] = {
            "fund_code": code,
            "fund_name": row.get("SHORTNAME", row.get("name")),
            "estimated_nav": _number(gsz),
            "estimated_change_pct": _number(gszzl),
            "latest_nav": _number(nav),
            "valuation_time": row.get("GZTIME", row.get("gztime")),
            "nav_date": row.get("PDATE", row.get("jzrq")),
            "source": "tiantian-fund-valuation-last",
            "provider_status": "available" if gsz not in (None, "") else "unavailable",
        }
    return result


def _number(value: Any) -> float | None:
    if value in (None, "", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
