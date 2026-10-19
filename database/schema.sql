CREATE TABLE IF NOT EXISTS customers (
    customer_key VARCHAR(191) PRIMARY KEY,
    customer_name TEXT NOT NULL,
    operator VARCHAR(16) NOT NULL,
    CONSTRAINT chk_customers_operator CHECK(operator IN ('SETU','KHT','BLORA','WUNUT','OFF'))
);

CREATE TABLE IF NOT EXISTS sales (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    report_date DATE NOT NULL,
    customer_key VARCHAR(191) NOT NULL,
    so DOUBLE NOT NULL DEFAULT 0,
    actual DOUBLE NOT NULL DEFAULT 0,
    source_file VARCHAR(255),
    imported_at TEXT NOT NULL,
    UNIQUE(report_date, customer_key),
    FOREIGN KEY(customer_key) REFERENCES customers(customer_key)
);

CREATE TABLE IF NOT EXISTS monthly_so_targets (
    month_start DATE NOT NULL PRIMARY KEY,
    so DOUBLE NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_history (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    imported_at TEXT NOT NULL,
    rows_read BIGINT NOT NULL DEFAULT 0,
    rows_saved BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    message TEXT
);

CREATE TABLE IF NOT EXISTS weekly_average_price_inputs (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    week_start DATE NOT NULL,
    customer_key VARCHAR(191) NOT NULL,
    region VARCHAR(80) NOT NULL,
    volume_mmbtu DOUBLE NOT NULL DEFAULT 0,
    price_usd_per_sm3 DOUBLE NOT NULL DEFAULT 0,
    exchange_rate DOUBLE NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    UNIQUE(week_start, customer_key),
    FOREIGN KEY(customer_key) REFERENCES customers(customer_key)
);

CREATE TABLE IF NOT EXISTS monthly_average_price_inputs (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    month_start DATE NOT NULL,
    customer_key VARCHAR(191) NOT NULL,
    region VARCHAR(80) NOT NULL,
    price_unit VARCHAR(16) NOT NULL DEFAULT 'USD_MMBTU',
    price_usd_per_mmbtu DOUBLE NOT NULL DEFAULT 0,
    price_rp_per_sm3 DOUBLE NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    UNIQUE(month_start, customer_key),
    FOREIGN KEY(customer_key) REFERENCES customers(customer_key)
);

CREATE TABLE IF NOT EXISTS monthly_average_price_operator_factors (
    month_start DATE NOT NULL,
    operator VARCHAR(16) NOT NULL,
    sm3_per_mmbtu DOUBLE NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(month_start, operator)
);

CREATE TABLE IF NOT EXISTS monthly_average_price_exchange_rates (
    month_start DATE NOT NULL PRIMARY KEY,
    exchange_rate DOUBLE NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monthly_average_price_targets (
    month_start DATE NOT NULL,
    region VARCHAR(32) NOT NULL,
    target_price_rp_sm3 DOUBLE NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(month_start, region)
);

CREATE TABLE IF NOT EXISTS complaints (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    report_date DATE NOT NULL,
    customer VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    follow_up TEXT NOT NULL,
    complaint_type VARCHAR(64) NOT NULL,
    priority VARCHAR(32) NOT NULL,
    status VARCHAR(16) NOT NULL,
    status_changed_at VARCHAR(19) NULL,
    resolution TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    INDEX idx_complaints_report_date (report_date)
);

CREATE TABLE IF NOT EXISTS app_users (
    username VARCHAR(191) PRIMARY KEY,
    password_hash TEXT NOT NULL
);
