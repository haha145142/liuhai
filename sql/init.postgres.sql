-- Fund Watch P0 · PostgreSQL / Neon
-- Run against the Neon database selected in DATABASE_URL.

CREATE TABLE IF NOT EXISTS fund_info (
  id BIGSERIAL PRIMARY KEY,
  fund_code VARCHAR(10) NOT NULL UNIQUE,
  fund_name VARCHAR(100) NOT NULL,
  short_name VARCHAR(50),
  fund_type SMALLINT NOT NULL DEFAULT 2,
  pinyin VARCHAR(50),
  manager VARCHAR(50),
  company VARCHAR(100),
  management_fee NUMERIC(8,4) DEFAULT 0,
  custodian_fee NUMERIC(8,4) DEFAULT 0,
  total_shares NUMERIC(20,2),
  nav NUMERIC(10,4),
  nav_date DATE,
  establish_date DATE,
  is_index SMALLINT DEFAULT 0,
  status SMALLINT DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fund_type ON fund_info(fund_type);
CREATE INDEX IF NOT EXISTS idx_fund_pinyin ON fund_info(pinyin);

CREATE TABLE IF NOT EXISTS fund_nav_history (
  id BIGSERIAL PRIMARY KEY,
  fund_code VARCHAR(10) NOT NULL REFERENCES fund_info(fund_code) ON DELETE CASCADE,
  nav_date DATE NOT NULL,
  nav NUMERIC(10,4) NOT NULL,
  acc_nav NUMERIC(10,4),
  daily_return NUMERIC(10,6),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(fund_code, nav_date)
);
CREATE INDEX IF NOT EXISTS idx_nav_date ON fund_nav_history(nav_date);

CREATE TABLE IF NOT EXISTS fund_holding (
  id BIGSERIAL PRIMARY KEY,
  fund_code VARCHAR(10) NOT NULL REFERENCES fund_info(fund_code) ON DELETE CASCADE,
  report_date DATE NOT NULL,
  report_type SMALLINT NOT NULL,
  stock_code VARCHAR(10),
  stock_name VARCHAR(50),
  security_type SMALLINT DEFAULT 1,
  industry_code VARCHAR(20),
  industry_name VARCHAR(30),
  weight NUMERIC(10,6) NOT NULL,
  market_value NUMERIC(20,2),
  is_top_ten SMALLINT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_holding_fund_report ON fund_holding(fund_code, report_date);
CREATE INDEX IF NOT EXISTS idx_holding_stock ON fund_holding(stock_code);

CREATE TABLE IF NOT EXISTS fund_industry_alloc (
  id BIGSERIAL PRIMARY KEY,
  fund_code VARCHAR(10) NOT NULL REFERENCES fund_info(fund_code) ON DELETE CASCADE,
  report_date DATE NOT NULL,
  industry_code VARCHAR(20) NOT NULL,
  industry_name VARCHAR(30) NOT NULL,
  weight NUMERIC(10,6) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(fund_code, report_date, industry_code)
);

CREATE TABLE IF NOT EXISTS watchlist_group (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL DEFAULT 1,
  group_name VARCHAR(50) NOT NULL,
  sort_order INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_watch_user ON watchlist_group(user_id);

CREATE TABLE IF NOT EXISTS watchlist_item (
  id BIGSERIAL PRIMARY KEY,
  group_id BIGINT NOT NULL REFERENCES watchlist_group(id) ON DELETE CASCADE,
  fund_code VARCHAR(10) NOT NULL REFERENCES fund_info(fund_code) ON DELETE CASCADE,
  sort_order INT DEFAULT 0,
  added_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(group_id, fund_code)
);
CREATE INDEX IF NOT EXISTS idx_watch_fund ON watchlist_item(fund_code);

CREATE TABLE IF NOT EXISTS estimated_nav_snapshot (
  id BIGSERIAL PRIMARY KEY,
  fund_code VARCHAR(10) NOT NULL REFERENCES fund_info(fund_code) ON DELETE CASCADE,
  trade_date DATE NOT NULL,
  snapshot_time TIMESTAMPTZ NOT NULL,
  est_nav NUMERIC(10,4) NOT NULL,
  est_change_pct NUMERIC(10,4),
  official_nav NUMERIC(10,4),
  deviation NUMERIC(10,4),
  model_version VARCHAR(20) DEFAULT 'v1',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_snapshot_fund_time ON estimated_nav_snapshot(fund_code, trade_date, snapshot_time);

CREATE TABLE IF NOT EXISTS market_index_quote (
  id BIGSERIAL PRIMARY KEY,
  index_code VARCHAR(20) NOT NULL,
  quote_date DATE NOT NULL,
  pre_close NUMERIC(10,4),
  last_price NUMERIC(10,4),
  change_pct NUMERIC(10,4),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(index_code, quote_date)
);

CREATE TABLE IF NOT EXISTS industry_quote (
  id BIGSERIAL PRIMARY KEY,
  industry_code VARCHAR(20) NOT NULL,
  industry_name VARCHAR(30),
  quote_date DATE NOT NULL,
  change_pct NUMERIC(10,4),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(industry_code, quote_date)
);

CREATE TABLE IF NOT EXISTS estimation_accuracy (
  id BIGSERIAL PRIMARY KEY,
  fund_code VARCHAR(10) NOT NULL REFERENCES fund_info(fund_code) ON DELETE CASCADE,
  trade_date DATE NOT NULL,
  est_change_pct NUMERIC(10,4),
  official_change_pct NUMERIC(10,4),
  absolute_error NUMERIC(10,4),
  is_suspicious SMALLINT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(fund_code, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_accuracy_error ON estimation_accuracy(absolute_error);

INSERT INTO watchlist_group(user_id, group_name, sort_order)
SELECT 1, '我的自选', 0
WHERE NOT EXISTS (SELECT 1 FROM watchlist_group WHERE user_id=1 AND group_name='我的自选');
