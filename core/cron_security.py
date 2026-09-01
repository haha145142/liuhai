"""Helpers for protecting scheduled Vercel endpoints."""
from __future__ import annotations

import hmac
import os


def authorized(authorization: str | None) -> bool:
    """Validate Vercel's Authorization header against CRON_SECRET."""
    secret = os.getenv("CRON_SECRET")
    if not secret or not authorization:
        return False
    expected = f"Bearer {secret}"
    return hmac.compare_digest(authorization, expected)
