"""Minimal PostgreSQL end-to-end smoke test.

Usage:
  DATABASE_URL='postgres://postgres:123456@localhost:5432/postgres' python sql/test_e2e_pg.py
"""
from pathlib import Path
import os

import psycopg

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (ROOT / 'sql' / 'init_pg.sql').read_text(encoding='utf-8')
URL = os.environ.get('DATABASE_URL')
if not URL:
    raise SystemExit('DATABASE_URL is required')

REQUIRED = [
    'fund_info', 'fund_nav', 'fund_holding', 'fund_industry_alloc',
    'watchlist_group', 'watchlist_item', 'estimated_nav_snapshot',
    'market_index_quote', 'industry_quote', 'stock_realtime_quote',
    'estimation_accuracy', 'sync_log',
]

with psycopg.connect(URL, autocommit=True) as conn:
    conn.execute(SCHEMA)
    for table in REQUIRED:
        row = conn.execute(
            "SELECT to_regclass(%s) AS name", (table,)
        ).fetchone()
        if not row or row[0] is None:
            raise AssertionError(f'missing table: {table}')

    conn.execute(
        "INSERT INTO fund_info(fund_code,fund_name,fund_type,nav) VALUES (%s,%s,%s,%s) "
        "ON CONFLICT (fund_code) DO UPDATE SET fund_name=EXCLUDED.fund_name, nav=EXCLUDED.nav",
        ('TEST001', 'Fund Watch E2E', 3, 1.2345),
    )
    got = conn.execute(
        'SELECT fund_name, nav FROM fund_info WHERE fund_code=%s', ('TEST001',)
    ).fetchone()
    assert got[0] == 'Fund Watch E2E'
    assert float(got[1]) == 1.2345
    conn.execute('DELETE FROM fund_info WHERE fund_code=%s', ('TEST001',))

print(f'PASS: PostgreSQL E2E smoke test; {len(REQUIRED)} tables created and CRUD verified.')
