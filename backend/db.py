import hashlib
from pathlib import Path


def initialize_database(connection_factory, app_username, app_password):
    schema_path = Path(__file__).resolve().parent.parent / "database" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")
    with connection_factory() as con:
        for statement in schema.split(";"):
            if statement.strip():
                con.execute(statement)

        user_columns = con.execute(
            """
            SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'app_users'
            """
        ).fetchall()
        if not any(column["COLUMN_NAME"] == "role" for column in user_columns):
            con.execute(
                "ALTER TABLE app_users ADD COLUMN role VARCHAR(16) "
                "NOT NULL DEFAULT 'division'"
            )

        average_price_columns = con.execute(
            """
            SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'monthly_average_price_inputs'
            """
        ).fetchall()
        average_price_column_names = {
            column["COLUMN_NAME"] for column in average_price_columns
        }
        if "price_unit" not in average_price_column_names:
            con.execute(
                "ALTER TABLE monthly_average_price_inputs "
                "ADD COLUMN price_unit VARCHAR(16) NOT NULL DEFAULT 'USD_MMBTU' "
                "AFTER region"
            )
        if "price_rp_per_sm3" not in average_price_column_names:
            con.execute(
                "ALTER TABLE monthly_average_price_inputs "
                "ADD COLUMN price_rp_per_sm3 DOUBLE NOT NULL DEFAULT 0 "
                "AFTER price_usd_per_mmbtu"
            )
        for column_name in (
            "sm3_override",
            "mmbtu_override",
            "total_usd_override",
            "rupiah_override",
        ):
            if column_name not in average_price_column_names:
                con.execute(
                    f"ALTER TABLE monthly_average_price_inputs "
                    f"ADD COLUMN {column_name} DOUBLE NULL"
                )
        if "include_in_summary" not in average_price_column_names:
            con.execute(
                "ALTER TABLE monthly_average_price_inputs "
                "ADD COLUMN include_in_summary BOOLEAN NOT NULL DEFAULT TRUE "
                "AFTER rupiah_override"
            )

        legacy_weekly_customers = (
            ("clin", "CLIN", "SETU"),
            ("abckogen", "ABC KOGEN", "KHT"),
        )
        for customer_key, customer_name, operator in legacy_weekly_customers:
            con.execute(
                "INSERT INTO customers (customer_key,customer_name,operator) "
                "VALUES (%s,%s,%s) ON DUPLICATE KEY UPDATE "
                "customer_name=VALUES(customer_name),operator=VALUES(operator)",
                (customer_key, customer_name, operator),
            )
        legacy_weekly_inputs = (
            ("2026-10-26", "clin", "JAWA BARAT", 959.0, 1.0, 958.0, "2026-10-14T09:59:48"),
            ("2026-10-26", "abckogen", "JAWA BARAT", 0.0, 13.4, 17.0, "2026-10-15T16:23:05"),
        )
        for week_start, customer_key, region, volume_mmbtu, price_usd, exchange_rate, updated_at in legacy_weekly_inputs:
            con.execute(
                "INSERT INTO weekly_average_price_inputs "
                "(week_start,customer_key,region,volume_mmbtu,price_usd_per_sm3,exchange_rate,updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                "region=VALUES(region),volume_mmbtu=VALUES(volume_mmbtu),"
                "price_usd_per_sm3=VALUES(price_usd_per_sm3),"
                "exchange_rate=VALUES(exchange_rate),updated_at=VALUES(updated_at)",
                (week_start, customer_key, region, volume_mmbtu, price_usd, exchange_rate, updated_at),
            )

        complaint_columns = con.execute(
            """
            SELECT COLUMN_NAME FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'complaints'
            """
        ).fetchall()
        if not any(column["COLUMN_NAME"] == "status_changed_at" for column in complaint_columns):
            con.execute(
                "ALTER TABLE complaints ADD COLUMN status_changed_at VARCHAR(19) NULL AFTER status"
            )
        con.execute(
            "ALTER TABLE complaints MODIFY status_changed_at VARCHAR(19) NULL"
        )
        con.execute(
            "UPDATE complaints SET status_changed_at="
            "CASE WHEN status='Closed' THEN COALESCE(status_changed_at,LEFT(updated_at,19)) "
            "ELSE NULL END"
        )

        checks = con.execute(
            """
            SELECT tc.CONSTRAINT_NAME, cc.CHECK_CLAUSE
            FROM information_schema.TABLE_CONSTRAINTS tc
            JOIN information_schema.CHECK_CONSTRAINTS cc
              ON cc.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
             AND cc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            WHERE tc.TABLE_SCHEMA = DATABASE()
              AND tc.TABLE_NAME = 'customers'
              AND tc.CONSTRAINT_TYPE = 'CHECK'
            """
        ).fetchall()
        operator_checks = [
            check for check in checks
            if "operator" in check["CHECK_CLAUSE"].lower()
        ]
        supports_off = any(
            "'off'" in check["CHECK_CLAUSE"].lower()
            or "\\'off\\'" in check["CHECK_CLAUSE"].lower()
            for check in operator_checks
        )
        if not supports_off:
            for check in operator_checks:
                constraint_name = check["CONSTRAINT_NAME"].replace("`", "``")
                con.execute(f"ALTER TABLE customers DROP CHECK `{constraint_name}`")
            con.execute(
                "ALTER TABLE customers ADD CONSTRAINT chk_customers_operator "
                "CHECK(operator IN ('SETU','KHT','BLORA','WUNUT','OFF'))"
            )

        password_hash = hashlib.sha256(app_password.encode("utf-8")).hexdigest()
        con.execute(
            "INSERT INTO app_users(username,password_hash,role) VALUES(%s,%s,'admin') "
            "ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash),role='admin'",
            (app_username, password_hash),
        )
