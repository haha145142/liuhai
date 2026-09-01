"""Small, serverless-safe PostgreSQL access layer for Fund Watch.

The module deliberately avoids an in-process ORM/session lifecycle. Each
request obtains a short-lived connection when DATABASE_URL is configured.
This works in Vercel Functions and keeps the application usable in demo mode.
"""
from __future__ import annotations

import os
from typing import Any

import psycopg


DATABASE_URL = os.getenv("DATABASE_URL")


def configured() -> bool:
    """Return True when PostgreSQL has been configured."""
    return bool(DATABASE_URL)


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Execute a read query and return rows as dictionaries."""
    if not DATABASE_URL:
        return []
    with psycopg.connect(DATABASE_URL, connect_timeout=4) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description is None:
                return []
            columns = [column.name for column in cur.description]
            return [dict(zip(columns, row)) for row in cur.fetchall()]


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    """Execute a write statement in a short-lived transaction."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    with psycopg.connect(DATABASE_URL, connect_timeout=4) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
        conn.commit()
