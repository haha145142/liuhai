-- Optional compatibility migration for existing Fund Watch code.
CREATE OR REPLACE VIEW fund_nav_history AS
SELECT fund_code, trade_date AS nav_date, est_nav AS nav
FROM estimated_nav_snapshot;
