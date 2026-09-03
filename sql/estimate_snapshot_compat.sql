-- Optional compatibility migration for existing Fund Watch code.
-- The canonical schema already uses estimated_nav_snapshot; this view keeps
-- older tooling that expects fund_nav_history working without duplicating data.
CREATE OR REPLACE VIEW fund_nav_history AS
SELECT fund_code, trade_date AS nav_date, est_nav AS nav
FROM estimated_nav_snapshot;
