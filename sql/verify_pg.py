from pathlib import Path

SQL = Path(__file__).with_name('init_pg.sql').read_text(encoding='utf-8')

BLACKLIST = ['AUTO_INCREMENT', 'ENGINE=INNODB', '`', 'DATETIME', 'TINYINT(']
REQUIRED = {
    'fund_info', 'fund_nav', 'fund_holding', 'fund_industry_alloc',
    'watchlist_group', 'watchlist_item', 'estimated_nav_snapshot',
    'market_index_quote', 'industry_quote', 'stock_realtime_quote',
    'estimation_accuracy', 'sync_log',
}

upper = SQL.upper()
errors = [word for word in BLACKLIST if word in upper]
missing = [name for name in REQUIRED if f'CREATE TABLE IF NOT EXISTS {name}' not in SQL]

if errors:
    raise SystemExit(f'MySQL remnants found: {errors}')
if missing:
    raise SystemExit(f'Missing tables: {missing}')
if 'CREATE OR REPLACE FUNCTION set_updated_at()' not in SQL:
    raise SystemExit('Missing updated_at trigger function')
if 'CREATE TRIGGER trg_fund_info_updated_at' not in SQL:
    raise SystemExit('Missing fund_info trigger')

print(f'PASS: PostgreSQL schema verified; {len(REQUIRED)} tables present; no MySQL remnants.')
