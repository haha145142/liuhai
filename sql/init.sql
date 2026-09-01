-- ============================================================
-- 基金看盘软件 P0 版本 · 数据库初始化脚本
-- 数据库：MySQL 8.0+  字符集：utf8mb4
-- 用法：mysql -u root -p < init.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS fund_watch
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_general_ci;

USE fund_watch;

CREATE TABLE IF NOT EXISTS fund_info (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    fund_code VARCHAR(10) NOT NULL UNIQUE,
    fund_name VARCHAR(100) NOT NULL,
    short_name VARCHAR(50),
    fund_type TINYINT NOT NULL,
    pinyin VARCHAR(50),
    manager VARCHAR(50),
    company VARCHAR(100),
    management_fee DECIMAL(8,4) DEFAULT 0,
    custodian_fee DECIMAL(8,4) DEFAULT 0,
    total_shares DECIMAL(20,2),
    nav DECIMAL(10,4),
    nav_date DATE,
    establish_date DATE,
    is_index TINYINT DEFAULT 0,
    status TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type (fund_type), INDEX idx_pinyin (pinyin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fund_nav_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    fund_code VARCHAR(10) NOT NULL,
    nav_date DATE NOT NULL,
    nav DECIMAL(10,4) NOT NULL,
    acc_nav DECIMAL(10,4),
    daily_return DECIMAL(10,6),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_fund_date (fund_code, nav_date), INDEX idx_date (nav_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fund_holding (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    fund_code VARCHAR(10) NOT NULL,
    report_date DATE NOT NULL,
    report_type TINYINT NOT NULL,
    stock_code VARCHAR(10),
    stock_name VARCHAR(50),
    security_type TINYINT DEFAULT 1,
    industry_code VARCHAR(20),
    industry_name VARCHAR(30),
    weight DECIMAL(10,6) NOT NULL,
    market_value DECIMAL(20,2),
    is_top_ten TINYINT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_fund_report (fund_code, report_date), INDEX idx_stock (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS fund_industry_alloc (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    fund_code VARCHAR(10) NOT NULL,
    report_date DATE NOT NULL,
    industry_code VARCHAR(20) NOT NULL,
    industry_name VARCHAR(30) NOT NULL,
    weight DECIMAL(10,6) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_fund_ind (fund_code, report_date, industry_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS watchlist_group (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL DEFAULT 1,
    group_name VARCHAR(50) NOT NULL,
    sort_order INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS watchlist_item (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    group_id BIGINT NOT NULL,
    fund_code VARCHAR(10) NOT NULL,
    sort_order INT DEFAULT 0,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_group_fund (group_id, fund_code), INDEX idx_fund (fund_code),
    CONSTRAINT fk_item_group FOREIGN KEY (group_id) REFERENCES watchlist_group(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS estimated_nav_snapshot (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    fund_code VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    snapshot_time DATETIME NOT NULL,
    est_nav DECIMAL(10,4) NOT NULL,
    est_change_pct DECIMAL(10,4),
    official_nav DECIMAL(10,4),
    deviation DECIMAL(10,4),
    model_version VARCHAR(20) DEFAULT 'v1',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_fund_date (fund_code, trade_date, snapshot_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS market_index_quote (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    index_code VARCHAR(20) NOT NULL,
    quote_date DATE NOT NULL,
    pre_close DECIMAL(10,4),
    last_price DECIMAL(10,4),
    change_pct DECIMAL(10,4),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_idx_date (index_code, quote_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS industry_quote (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    industry_code VARCHAR(20) NOT NULL,
    industry_name VARCHAR(30),
    quote_date DATE NOT NULL,
    change_pct DECIMAL(10,4),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ind_date (industry_code, quote_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS estimation_accuracy (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    fund_code VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    est_change_pct DECIMAL(10,4),
    official_change_pct DECIMAL(10,4),
    absolute_error DECIMAL(10,4),
    is_suspicious TINYINT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_fund_date (fund_code, trade_date), INDEX idx_error (absolute_error)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
