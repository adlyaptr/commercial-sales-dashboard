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
    sm3_override DOUBLE NULL,
    mmbtu_override DOUBLE NULL,
    total_usd_override DOUBLE NULL,
    rupiah_override DOUBLE NULL,
    include_in_summary BOOLEAN NOT NULL DEFAULT TRUE,
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

CREATE TABLE IF NOT EXISTS monthly_average_price_workbook_imports (
    month_start DATE NOT NULL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    imported_at TEXT NOT NULL,
    customer_keys_json LONGTEXT NOT NULL,
    summary_sm3 DOUBLE NOT NULL,
    summary_rupiah DOUBLE NOT NULL,
    summary_average_price DOUBLE NOT NULL
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
    password_hash TEXT NOT NULL,
    role VARCHAR(16) NOT NULL DEFAULT 'division',
    sph_role VARCHAR(32) NULL
);

CREATE TABLE IF NOT EXISTS sph_customers (
    customer_key VARCHAR(191) PRIMARY KEY,
    customer_name VARCHAR(255) NOT NULL,
    address_line1 TEXT NOT NULL,
    address_line2 TEXT NOT NULL,
    created_by VARCHAR(191) NOT NULL,
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS sph_sequences (
    month_key CHAR(7) PRIMARY KEY,
    next_value INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sph_proposals (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    proposal_number VARCHAR(80) NOT NULL UNIQUE,
    customer_key VARCHAR(191) NOT NULL,
    proposal_date DATE NOT NULL,
    volume_min DECIMAL(16,2) NOT NULL,
    volume_max DECIMAL(16,2) NOT NULL,
    price_usd DECIMAL(12,2) NOT NULL,
    status VARCHAR(24) NOT NULL,
    version INT NOT NULL DEFAULT 0,
    top_percent DECIMAL(5,2) NOT NULL DEFAULT 90,
    guarantee VARCHAR(64) NOT NULL,
    due_day TINYINT NOT NULL DEFAULT 20,
    exchange_clause BOOLEAN NOT NULL DEFAULT FALSE,
    contract_years TINYINT NOT NULL DEFAULT 2,
    reethau_obligations TEXT NOT NULL,
    customer_obligations TEXT NOT NULL,
    approvals TEXT NOT NULL,
    sent_date DATE NULL,
    approved_at DATE NULL,
    actual_volume DECIMAL(16,2) NULL,
    created_by VARCHAR(191) NOT NULL,
    updated_at DATETIME NOT NULL,
    INDEX idx_sph_proposals_status (status),
    INDEX idx_sph_proposals_customer (customer_key),
    CONSTRAINT fk_sph_proposals_customer
        FOREIGN KEY (customer_key) REFERENCES sph_customers(customer_key)
);

CREATE TABLE IF NOT EXISTS sph_proposal_logs (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    proposal_id BIGINT NOT NULL,
    actor_username VARCHAR(191) NOT NULL,
    actor_role VARCHAR(32) NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    INDEX idx_sph_proposal_logs_proposal (proposal_id, id),
    CONSTRAINT fk_sph_logs_proposal
        FOREIGN KEY (proposal_id) REFERENCES sph_proposals(id) ON DELETE CASCADE
);
