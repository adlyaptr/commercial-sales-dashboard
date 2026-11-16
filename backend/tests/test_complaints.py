import asyncio
import os
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class FakeRequest:
    def __init__(self, payload=None, authenticated=True, username=None, role=None):
        self.payload = payload or {}
        self.session = {"username": username or main.APP_USERNAME} if authenticated else {}
        if authenticated and role is not None:
            self.session["role"] = role

    async def json(self):
        return self.payload


class MemoryComplaints:
    columns = (
        "id,report_date,customer,summary,follow_up,complaint_type,priority,"
        "status,status_changed_at,resolution,updated_at"
    )

    def __init__(self):
        self.rows = []
        self.next_id = 1

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        parameters = parameters or ()
        if statement.startswith("SELECT report_date,status,complaint_type FROM complaints ORDER BY"):
            rows = sorted(
                self.rows,
                key=lambda row: (row["report_date"], row["id"]),
                reverse=True,
            )
            return SimpleNamespace(fetchall=lambda: [
                {
                    "report_date": row["report_date"],
                    "status": row["status"],
                    "complaint_type": row["complaint_type"],
                }
                for row in rows
            ])

        if statement.startswith(f"SELECT {self.columns} FROM complaints ORDER BY"):
            rows = sorted(
                self.rows,
                key=lambda row: (row["report_date"], row["id"]),
                reverse=True,
            )
            return SimpleNamespace(fetchall=lambda: rows)

        if statement.startswith(f"SELECT {self.columns} FROM complaints WHERE id="):
            row = next((item for item in self.rows if item["id"] == parameters[0]), None)
            return SimpleNamespace(fetchone=lambda: row)

        if statement.startswith("SELECT id FROM complaints WHERE report_date="):
            row = next(
                (
                    item
                    for item in self.rows
                    if (
                        item["report_date"].isoformat(),
                        item["customer"],
                        item["summary"],
                    ) == parameters
                ),
                None,
            )
            return SimpleNamespace(fetchone=lambda: row)

        if statement.startswith("SELECT id FROM complaints WHERE id="):
            row = next((item for item in self.rows if item["id"] == parameters[0]), None)
            return SimpleNamespace(fetchone=lambda: row)

        if statement == "SELECT 1":
            return SimpleNamespace(fetchone=lambda: {"1": 1})

        if statement.startswith("INSERT INTO complaints"):
            row = dict(zip(self.columns.split(","), (self.next_id, *parameters)))
            row["report_date"] = date.fromisoformat(row["report_date"])
            self.rows.append(row)
            self.next_id += 1
            return SimpleNamespace(lastrowid=row["id"], rowcount=1)

        if statement.startswith("UPDATE complaints SET"):
            complaint_id = parameters[-1]
            row = next((item for item in self.rows if item["id"] == complaint_id), None)
            if row is None:
                return SimpleNamespace(rowcount=0)
            values = dict(zip(self.columns.split(",")[1:], parameters[:-1]))
            values["report_date"] = date.fromisoformat(values["report_date"])
            row.update(values)
            return SimpleNamespace(rowcount=1)

        raise AssertionError(f"Unexpected SQL in test: {statement}")


class MemoryCustomerMappings:
    def __init__(self):
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if not statement.startswith("INSERT INTO customers"):
            raise AssertionError(f"Unexpected SQL in test: {statement}")
        self.rows.append(parameters)
        return SimpleNamespace(rowcount=1)


class MemoryDashboard:
    def __init__(
        self,
        actual_imported=True,
        sales_rows=None,
        imported_day_offset=1,
    ):
        self.actual_imported = actual_imported
        self.imported_day_offset = imported_day_offset
        self.sales_rows = sales_rows or [
            {"customer_key": "pelanggansetu", "customer_name": "Pelanggan Setu", "operator": "SETU", "so": 100, "actual": 120, "id": 1, "source_file": "daily.xlsx", "manual_fob": False},
            {"customer_key": "pelanggankht", "customer_name": "Pelanggan KHT", "operator": "KHT", "so": 0, "actual": 10, "id": 2, "source_file": "daily.xlsx", "manual_fob": False},
            {"customer_key": "pelangganoff", "customer_name": "Pelanggan OFF", "operator": "OFF", "so": 50, "actual": 20, "id": 3, "source_file": "daily.xlsx", "manual_fob": False},
        ]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        normalized_statement = statement.strip()
        if normalized_statement.startswith("SELECT c.customer_name, c.operator, c.customer_key"):
            return SimpleNamespace(fetchall=lambda: self.sales_rows)

        if normalized_statement.startswith(
            "SELECT report_date, imported_at FROM daily_actual_imports"
        ):
            report_date = date.fromisoformat(parameters[0])
            imported = {
                "report_date": report_date,
                "imported_at": datetime.combine(
                    report_date + timedelta(days=self.imported_day_offset),
                    datetime.min.time(),
                ),
            } if self.actual_imported else None
            return SimpleNamespace(fetchone=lambda: imported)

        if normalized_statement.startswith("SELECT customer_key, customer_name, operator FROM customers"):
            return SimpleNamespace(fetchall=lambda: [
                {"customer_key": "pelanggansetu", "customer_name": "Pelanggan Setu", "operator": "SETU"},
                {"customer_key": "pelanggankht", "customer_name": "Pelanggan KHT", "operator": "KHT"},
                {"customer_key": "pelangganoff", "customer_name": "Pelanggan OFF", "operator": "OFF"},
                {"customer_key": "pelangganforecast", "customer_name": "Pelanggan Forecast", "operator": "WUNUT"},
            ])

        if "AS period_start" in normalized_statement:
            return SimpleNamespace(fetchall=lambda: [
                {"period_start": date(2026, 1, 1), "so": 500, "actual": 450},
                {"period_start": date(2026, 10, 1), "so": 150, "actual": 150},
            ])

        if normalized_statement.startswith("SELECT filename, imported_at FROM import_history"):
            return SimpleNamespace(fetchone=lambda: None)

        raise AssertionError(f"Unexpected SQL in test: {statement}")


class MemoryLatestActualDate:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if "report_date <= %s" not in statement or not parameters:
            raise AssertionError("Latest actual date must exclude future dates.")
        cutoff = date.fromisoformat(parameters[0])
        latest_past_date = cutoff - timedelta(days=1)
        return SimpleNamespace(fetchone=lambda: {"report_date": latest_past_date})


class MemoryMonthlySummary:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if "AND s.report_date <= %s" not in statement:
            raise AssertionError("Monthly summary must apply the selected report-date limit.")
        if parameters != (2026, "2026-10-14"):
            raise AssertionError(f"Unexpected monthly query parameters: {parameters}")
        return SimpleNamespace(fetchall=lambda: [{
            "customer_key": "contoh",
            "customer_name": "Pelanggan Contoh",
            "operator": "SETU",
            "month_number": 10,
            "total_so": 100,
            "total_actual": 120,
        }])


class MemoryHomeSummary:
    def __init__(
        self,
        sales_rows=None,
        actual_imported_dates=("2026-10-05", "2026-10-06", "2026-10-07"),
    ):
        self.sales_rows = sales_rows or [
            {"report_date": date(2026, 10, 5), "customer_name": "SETU Customer", "operator": "SETU", "customer_key": "setu-a", "so": 100, "actual": 80},
            {"report_date": date(2026, 10, 6), "customer_name": "SETU Customer", "operator": "SETU", "customer_key": "setu-a", "so": 100, "actual": 90},
            {"report_date": date(2026, 10, 6), "customer_name": "KHT Customer", "operator": "KHT", "customer_key": "kht-a", "so": 0, "actual": 20},
            {"report_date": date(2026, 10, 7), "customer_name": "OFF Customer", "operator": "OFF", "customer_key": "off-a", "so": 50, "actual": 40},
        ]
        self.actual_imported_dates = {
            date.fromisoformat(value) for value in actual_imported_dates
        }

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if statement.startswith("SELECT so FROM monthly_so_targets"):
            return SimpleNamespace(fetchone=lambda: {"so": 1250})
        if statement.startswith("SELECT customer_key,customer_name,operator FROM customers"):
            return SimpleNamespace(fetchall=lambda: [
                {"customer_key": "setu-a", "customer_name": "SETU Customer", "operator": "SETU"},
                {"customer_key": "kht-a", "customer_name": "KHT Customer", "operator": "KHT"},
                {"customer_key": "off-a", "customer_name": "OFF Customer", "operator": "OFF"},
            ])
        if statement.startswith(
            "SELECT report_date, imported_at FROM daily_actual_imports"
        ):
            return SimpleNamespace(fetchall=lambda: [
                {
                    "report_date": report_date,
                    "imported_at": datetime.combine(
                        report_date + timedelta(days=1),
                        datetime.min.time(),
                    ),
                }
                for report_date in self.actual_imported_dates
            ])
        if "SELECT s.report_date, c.customer_name, c.operator" not in statement:
            raise AssertionError(f"Unexpected SQL in test: {statement}")
        if parameters != ("2026-01-01", "2026-10-31"):
            raise AssertionError(f"Unexpected home-summary date range: {parameters}")
        return SimpleNamespace(fetchall=lambda: self.sales_rows)


class MemoryHomeSummaryRange:
    def __init__(self, sales_rows=None, actual_imported_dates=None):
        self.sales_rows = sales_rows or [
            {"report_date": date(2026, 8, 5), "customer_name": "Customer Contoh", "operator": "SETU", "customer_key": "setu-a", "so": 100, "actual": 80, "source_file": "daily.xlsx"},
            {"report_date": date(2026, 10, 5), "customer_name": "Customer Contoh", "operator": "SETU", "customer_key": "setu-a", "so": 200, "actual": 180, "source_file": "daily.xlsx"},
            {"report_date": date(2026, 10, 6), "customer_name": "Customer Belum Dipetakan", "operator": "KHT", "customer_key": "kht-a", "so": 50, "actual": 40, "source_file": "daily.xlsx"},
            {"report_date": date(2026, 10, 7), "customer_name": "KTN", "operator": "KHT", "customer_key": "ktn", "so": 0, "actual": 10, "source_file": "daily.xlsx"},
            {"report_date": date(2026, 10, 8), "customer_name": "Blora Customer", "operator": "BLORA", "customer_key": "blora-a", "so": 0, "actual": 20, "source_file": "daily.xlsx"},
            {"report_date": date(2026, 10, 9), "customer_name": "Wunut Customer", "operator": "WUNUT", "customer_key": "wunut-a", "so": 0, "actual": 30, "source_file": "daily.xlsx"},
        ]
        if actual_imported_dates is None:
            actual_imported_dates = (
                "2026-08-05",
                "2026-10-05",
                "2026-10-06",
                "2026-10-07",
                "2026-10-08",
                "2026-10-09",
            )
        self.actual_imported_dates = {
            date.fromisoformat(value) if isinstance(value, str) else value
            for value in actual_imported_dates
        }

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if "FROM sales s" in statement and "WHERE s.report_date BETWEEN" in statement:
            return SimpleNamespace(fetchall=lambda: self.sales_rows)
        if statement.startswith(
            "SELECT report_date, imported_at FROM daily_actual_imports"
        ):
            return SimpleNamespace(fetchall=lambda: [
                {
                    "report_date": report_date,
                    "imported_at": datetime.combine(
                        report_date + timedelta(days=1),
                        datetime.min.time(),
                    ),
                }
                for report_date in self.actual_imported_dates
            ])
        if statement.startswith("SELECT customer_key,customer_name,operator FROM customers"):
            return SimpleNamespace(fetchall=lambda: [
                {"customer_key": "setu-a", "customer_name": "SETU Customer", "operator": "SETU"},
                {"customer_key": "kht-a", "customer_name": "KHT Customer", "operator": "KHT"},
                {"customer_key": "ktn", "customer_name": "KTN", "operator": "KHT"},
                {"customer_key": "blora-a", "customer_name": "Blora Customer", "operator": "BLORA"},
                {"customer_key": "wunut-a", "customer_name": "Wunut Customer", "operator": "WUNUT"},
            ])
        if statement.startswith("SELECT month_start,so FROM monthly_so_targets"):
            return SimpleNamespace(fetchall=lambda: [
                {"month_start": date(2026, 8, 1), "so": 500},
                {"month_start": date(2026, 9, 1), "so": 600},
                {"month_start": date(2026, 10, 1), "so": 700},
            ])
        raise AssertionError(f"Unexpected SQL in test: {statement}")


class MemoryMonthlySOTargets:
    def __init__(self):
        self.targets = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if statement.startswith("SELECT so FROM monthly_so_targets"):
            target = self.targets.get(parameters[0])
            return SimpleNamespace(fetchone=lambda: target)
        if statement.startswith("INSERT INTO monthly_so_targets"):
            self.targets[parameters[0]] = {
                "month_start": parameters[0],
                "so": parameters[1],
            }
            return SimpleNamespace(rowcount=1)
        raise AssertionError(f"Unexpected SQL in test: {statement}")


class MemoryImportHistory:
    def __init__(self):
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if not statement.startswith("INSERT INTO import_history"):
            raise AssertionError(f"Unexpected SQL in test: {statement}")
        self.rows.append(parameters)
        return SimpleNamespace(rowcount=1)


class ComplaintApiTests(unittest.TestCase):
    def setUp(self):
        self.database = MemoryComplaints()
        self.db_patch = patch.object(main, "db", return_value=self.database)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def complaint(self, **overrides):
        return {
            "date": "2026-10-13",
            "customer": "PT Contoh",
            "summary": "Keluhan pasokan",
            "followUp": "Ditindaklanjuti",
            "type": "Keterlambatan Pekerjaan",
            "priority": "Normal",
            "status": "Open",
            "resolution": "",
            **overrides,
        }

    def test_create_list_and_update_complaint(self):
        created = asyncio.run(main.create_complaint(FakeRequest(self.complaint())))
        self.assertEqual(created["id"], 1)
        self.assertEqual(created["customer"], "PT Contoh")
        self.assertEqual(created["date"], "2026-10-13")
        self.assertEqual(created["type"], "Keterlambatan Pekerjaan")
        self.assertIsNone(created["statusChangedAt"])

        updated = asyncio.run(main.update_complaint(
            1,
            FakeRequest(self.complaint(
                summary="Keluhan selesai",
                status="Closed",
                statusChangedAt="2026-10-15",
            )),
        ))
        self.assertEqual(updated["summary"], "Keluhan selesai")
        self.assertEqual(updated["status"], "Closed")
        self.assertEqual(updated["statusChangedAt"], "2026-10-15")

        listed = main.list_complaints(FakeRequest())
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], 1)
        self.assertEqual(listed[0]["statusChangedAt"], updated["statusChangedAt"])

    def test_new_and_existing_complaint_categories_are_accepted(self):
        for complaint_type in main.COMPLAINT_TYPES:
            with self.subTest(complaint_type=complaint_type):
                fields = main.normalize_complaint(self.complaint(type=complaint_type))
                self.assertEqual(fields[4], complaint_type)

        for complaint_type in main.LEGACY_COMPLAINT_TYPES:
            with self.subTest(complaint_type=complaint_type):
                fields = main.normalize_complaint(self.complaint(type=complaint_type))
                self.assertEqual(fields[4], complaint_type)

    def test_closed_status_date_is_only_set_on_close_and_stays_stable(self):
        class SequencedDateTime(datetime):
            call_count = 0

            @classmethod
            def now(cls, tz=None):
                cls.call_count += 1
                return cls(2026, 10, 13, 10, 0, cls.call_count)

        with patch.object(main, "datetime", SequencedDateTime):
            created = asyncio.run(main.create_complaint(FakeRequest(self.complaint())))
            unchanged_status = asyncio.run(main.update_complaint(
                created["id"],
                FakeRequest(self.complaint(summary="Ringkasan diperbarui")),
            ))
            monitoring = asyncio.run(main.update_complaint(
                created["id"],
                FakeRequest(self.complaint(status="Monitoring")),
            ))
            closed = asyncio.run(main.update_complaint(
                created["id"],
                FakeRequest(self.complaint(status="Closed", statusChangedAt="2026-10-12")),
            ))
            closed_edit = asyncio.run(main.update_complaint(
                created["id"],
                FakeRequest(self.complaint(status="Closed", statusChangedAt="2026-10-12", summary="Sudah ditutup")),
            ))
            reopened = asyncio.run(main.update_complaint(
                created["id"],
                FakeRequest(self.complaint(status="Open")),
            ))
            closed_again = asyncio.run(main.update_complaint(
                created["id"],
                FakeRequest(self.complaint(status="Closed", statusChangedAt="2026-10-14")),
            ))

        self.assertIsNone(created["statusChangedAt"])
        self.assertIsNone(unchanged_status["statusChangedAt"])
        self.assertEqual(monitoring["status"], "Monitoring")
        self.assertIsNone(monitoring["statusChangedAt"])
        self.assertEqual(closed["status"], "Closed")
        self.assertEqual(closed["statusChangedAt"], "2026-10-12")
        self.assertEqual(closed_edit["statusChangedAt"], closed["statusChangedAt"])
        self.assertEqual(reopened["status"], "Open")
        self.assertIsNone(reopened["statusChangedAt"])
        self.assertEqual(closed_again["statusChangedAt"], "2026-10-14")

    def test_closed_complaint_requires_valid_closing_date(self):
        with self.assertRaises(main.HTTPException) as missing_date:
            asyncio.run(main.create_complaint(
                FakeRequest(self.complaint(status="Closed"))
            ))
        self.assertEqual(missing_date.exception.status_code, 400)

        with self.assertRaises(main.HTTPException) as invalid_date:
            asyncio.run(main.create_complaint(
                FakeRequest(self.complaint(status="Closed", statusChangedAt="tanggal"))
            ))
        self.assertEqual(invalid_date.exception.status_code, 400)

    def test_public_complaint_list_is_minimal_and_mutations_require_login(self):
        with self.assertRaises(main.HTTPException) as invalid:
            asyncio.run(main.create_complaint(FakeRequest(self.complaint(date="tanggal"))))
        self.assertEqual(invalid.exception.status_code, 400)

        with self.assertRaises(main.HTTPException) as invalid_status:
            asyncio.run(main.create_complaint(FakeRequest(self.complaint(status="Resolved"))))
        self.assertEqual(invalid_status.exception.status_code, 400)

        with self.assertRaises(main.HTTPException) as unauthenticated:
            asyncio.run(main.create_complaint(
                FakeRequest(self.complaint(), authenticated=False)
            ))
        self.assertEqual(unauthenticated.exception.status_code, 401)

        asyncio.run(main.create_complaint(FakeRequest(self.complaint())))
        public_complaints = main.list_complaints(FakeRequest(authenticated=False))
        self.assertEqual(public_complaints, [{
            "date": "2026-10-13",
            "status": "Open",
            "type": "Keterlambatan Pekerjaan",
        }])

    def test_user_role_can_view_full_complaint_details(self):
        asyncio.run(main.create_complaint(FakeRequest(self.complaint())))
        request = FakeRequest(username="reader", role="user")
        with patch.object(main, "require_home_access"):
            result = main.list_complaints(request)
        self.assertEqual(result[0]["customer"], "PT Contoh")
        self.assertEqual(result[0]["summary"], "Keluhan pasokan")
        self.assertIn("resolution", result[0])

    def test_legacy_import_is_safe_to_retry(self):
        legacy = self.complaint()
        first = asyncio.run(main.import_legacy_complaints(
            FakeRequest({"complaints": [legacy]})
        ))
        second = asyncio.run(main.import_legacy_complaints(
            FakeRequest({"complaints": [legacy]})
        ))

        self.assertEqual(first, {"imported": 1, "skipped": 0})
        self.assertEqual(second, {"imported": 0, "skipped": 1})
        self.assertEqual(len(self.database.rows), 1)

    def test_health_endpoint_checks_database_connectivity(self):
        self.assertEqual(main.health(), {"status": "ok", "database": "connected"})

    def test_production_configuration_requires_secure_session_and_strong_secrets(self):
        environment = {
            "DATABASE_URL": "mysql://dashboard_user:secret@127.0.0.1:3306/commercial_sales_dashboard",
            "APP_USERNAME": "dashboard",
            "APP_PASSWORD": "unique-production-password",
            "SESSION_SECRET": "random-production-session-secret-with-enough-length",
        }
        with patch.dict(os.environ, environment, clear=True):
            with patch.multiple(
                main,
                APP_ENV="production",
                APP_PASSWORD=environment["APP_PASSWORD"],
                SESSION_SECRET=environment["SESSION_SECRET"],
                SESSION_COOKIE_SECURE=False,
            ):
                with self.assertRaises(RuntimeError):
                    main.validate_runtime_config()
            with patch.multiple(
                main,
                APP_ENV="production",
                APP_PASSWORD=environment["APP_PASSWORD"],
                SESSION_SECRET=environment["SESSION_SECRET"],
                SESSION_COOKIE_SECURE=True,
            ):
                main.validate_runtime_config()

    def test_customer_mapping_accepts_off_and_rejects_unknown_status(self):
        self.assertEqual(
            main.normalize_customer_mapping("  Customer Baru ", "off"),
            ("customerbaru", "Customer Baru", "OFF"),
        )
        self.assertEqual(
            main.normalize_customer_mapping("Customer Reguler", "SETU"),
            ("customerreguler", "Customer Reguler", "SETU"),
        )
        with self.assertRaises(main.HTTPException) as invalid:
            main.normalize_customer_mapping("Customer Baru", "TIDAK AKTIF")
        self.assertEqual(invalid.exception.status_code, 400)

    def test_customer_mapping_api_persists_off_assignment(self):
        mappings_database = MemoryCustomerMappings()
        payload = {
            "mappings": [{"customer": "Customer Nonaktif", "operator": "OFF"}],
        }
        with patch.object(main, "db", return_value=mappings_database):
            result = asyncio.run(main.save_customer_mappings(FakeRequest(payload)))

        self.assertEqual(result, {"ok": True, "saved": 1})
        self.assertEqual(
            mappings_database.rows,
            [("customernonaktif", "Customer Nonaktif", "OFF")],
        )


class DashboardApiTests(unittest.TestCase):
    def setUp(self):
        self.db_patch = patch.object(main, "db", return_value=MemoryDashboard())
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.sales_order_patch = patch.object(main, "get_sales_order_data", return_value={})
        self.sales_order_patch.start()
        self.addCleanup(self.sales_order_patch.stop)

    def test_dashboard_returns_sales_totals_and_fills_monthly_trend(self):
        result = main.dashboard(
            FakeRequest(),
            report_date="2026-10-14",
            trend_period="monthly",
        )

        self.assertEqual(result["total_so"], 150)
        self.assertEqual(result["total_actual"], 150)
        self.assertEqual(result["diff"], 0)
        self.assertEqual(result["customer_active"], 2)
        self.assertEqual(result["operator_totals"]["SETU"]["diff"], 20)
        self.assertEqual(result["operator_totals"]["OFF"]["customers"], 1)
        self.assertEqual(len(result["trend"]), 12)
        self.assertEqual(result["trend"][0]["period_start"], "2025-11-01")
        self.assertFalse(result["trend"][0]["has_data"])
        self.assertEqual(result["trend"][-1]["period_start"], "2026-10-01")
        self.assertTrue(result["trend"][-1]["has_data"])
        self.assertEqual(result["trend"][-1]["actual"], 150)

    def test_dashboard_preserves_imported_so_and_actual_when_date_has_actuals(self):
        sales_orders = {
            "2026-10-14": [
                {"customer": "Pelanggan Setu", "so": 140},
                {"customer": "Pelanggan KHT", "so": 60},
            ],
        }
        with patch.object(main, "get_sales_order_data", return_value=sales_orders):
            result = main.dashboard(
                FakeRequest(),
                report_date="2026-10-14",
                trend_period="monthly",
            )

        self.assertEqual(result["total_so"], 150)
        self.assertEqual(result["total_actual"], 150)
        setu = result["operators"]["SETU"][0]
        self.assertEqual(setu["so"], 100)
        self.assertEqual(setu["actual"], 120)

    def test_dashboard_keeps_zero_actual_when_date_has_actual_import(self):
        database = MemoryDashboard(
            actual_imported=True,
            sales_rows=[{
                "customer_key": "pelangganforecast",
                "customer_name": "Pelanggan Forecast",
                "operator": "WUNUT",
                "so": 500,
                "actual": 0,
                "id": 7,
                "source_file": "daily.xlsx",
                "manual_fob": False,
            }],
        )
        sales_orders = {
            "2026-10-14": [
                {"customer": "Pelanggan Forecast", "so": 700},
            ],
        }
        with (
            patch.object(main, "db", return_value=database),
            patch.object(main, "get_sales_order_data", return_value=sales_orders),
        ):
            result = main.dashboard(
                FakeRequest(),
                report_date="2026-10-14",
                trend_period="monthly",
            )

        forecast_customer = result["operators"]["WUNUT"][0]
        self.assertEqual(forecast_customer["so"], 500)
        self.assertEqual(forecast_customer["actual"], 0)
        self.assertFalse(forecast_customer["actual_is_forecast"])

    def test_dashboard_forecasts_stale_actual_when_date_has_no_actual_import(self):
        database = MemoryDashboard(
            actual_imported=False,
            sales_rows=[{
                "customer_key": "pelangganforecast",
                "customer_name": "Pelanggan Forecast",
                "operator": "WUNUT",
                "so": 500,
                "actual": 120,
                "id": 7,
                "source_file": "planner.xlsx",
                "manual_fob": False,
            }],
        )
        sales_orders = {
            "2026-10-14": [
                {"customer": "Pelanggan Forecast", "so": 700},
            ],
        }
        with (
            patch.object(main, "db", return_value=database),
            patch.object(main, "get_sales_order_data", return_value=sales_orders),
        ):
            result = main.dashboard(
                FakeRequest(),
                report_date="2026-10-14",
                trend_period="monthly",
            )

        forecast_customer = result["operators"]["WUNUT"][0]
        self.assertEqual(forecast_customer["so"], 700)
        self.assertEqual(forecast_customer["actual"], 700)
        self.assertTrue(forecast_customer["actual_is_forecast"])

    def test_dashboard_forecasts_same_day_actual_import(self):
        database = MemoryDashboard(
            actual_imported=True,
            imported_day_offset=0,
            sales_rows=[{
                "customer_key": "pelangganforecast",
                "customer_name": "Pelanggan Forecast",
                "operator": "WUNUT",
                "so": 0,
                "actual": 10000,
                "id": 1,
                "source_file": "daily.xlsx",
                "manual_fob": False,
            }],
        )
        sales_orders = {
            "2026-10-14": [
                {"customer": "Pelanggan Forecast", "so": 700},
            ],
        }
        with (
            patch.object(main, "db", return_value=database),
            patch.object(main, "get_sales_order_data", return_value=sales_orders),
        ):
            result = main.dashboard(
                FakeRequest(),
                report_date="2026-10-14",
                trend_period="monthly",
            )

        forecast_customer = result["operators"]["WUNUT"][0]
        self.assertEqual(forecast_customer["so"], 700)
        self.assertEqual(forecast_customer["actual"], 700)
        self.assertTrue(forecast_customer["actual_is_forecast"])

    def test_dashboard_rejects_unknown_trend_period(self):
        with self.assertRaises(main.HTTPException) as invalid:
            main.dashboard(
                FakeRequest(),
                report_date="2026-10-14",
                trend_period="quarterly",
            )
        self.assertEqual(invalid.exception.status_code, 400)

    def test_monthly_summary_can_stop_at_selected_date(self):
        with patch.object(main, "db", return_value=MemoryMonthlySummary()):
            result = main.monthly_summary(
                FakeRequest(),
                year=2026,
                through_date="2026-10-14",
            )

        self.assertEqual(result["through_date"], "2026-10-14")
        self.assertEqual(result["items"][0]["actual"], 120)

    def test_latest_actual_date_excludes_future_actual_rows(self):
        with patch.object(main, "db", return_value=MemoryLatestActualDate()):
            result = main.latest_actual_date(FakeRequest())

        self.assertEqual(
            result,
            (main._business_today() - timedelta(days=1)).isoformat(),
        )


class HomeSummaryTests(unittest.TestCase):
    def test_home_summary_range_uses_imported_actuals_for_regional_volumes(self):
        with (
            patch.object(main, "db", return_value=MemoryHomeSummaryRange()),
            patch.object(main, "get_sales_order_data", return_value={}) as get_sales_order_data,
        ):
            result = main.home_summary_range(
                FakeRequest(),
                start_date="2026-08-01",
                end_date="2026-10-31",
            )

        self.assertEqual(
            [item["manual_so"] for item in result["year_months"]],
            [500, 600, 700],
        )
        self.assertFalse(result["year_months"][1]["has_data"])
        self.assertEqual(result["month_summary"]["manual_so"], 1800)
        self.assertEqual(result["summary_report"], {"so": 350, "actual": 360})
        self.assertEqual(result["regional_volumes"], [
            {"region": "JAWA BARAT", "actual_sm3": 300.0},
            {"region": "JAWA TENGAH", "actual_sm3": 30.0},
            {"region": "JAWA TIMUR", "actual_sm3": 30.0},
        ])
        self.assertEqual(
            result["summary_report"]["actual"]
            - sum(row["actual_sm3"] for row in result["regional_volumes"]),
            0,
        )
        get_sales_order_data.assert_called_once()

    def test_home_summary_range_forecasts_unimported_actuals_only(self):
        database = MemoryHomeSummaryRange(
            sales_rows=[
                {
                    "report_date": date(2026, 10, 5),
                    "customer_name": "SETU Customer",
                    "operator": "SETU",
                    "customer_key": "setu-a",
                    "so": 200,
                    "actual": 100,
                    "source_file": "daily.xlsx",
                    "manual_fob": False,
                },
                {
                    "report_date": date(2026, 10, 6),
                    "customer_name": "KHT Customer",
                    "operator": "KHT",
                    "customer_key": "kht-a",
                    "so": 100,
                    "actual": 40,
                    "manual_fob": False,
                },
            ],
            actual_imported_dates=("2026-10-05",),
        )
        sales_orders = {
            "2026-10-05": [{"customer": "SETU Customer", "so": 900}],
            "2026-10-06": [{"customer": "KHT Customer", "so": 300}],
            "2026-10-07": [{"customer": "SETU Customer", "so": 400}],
        }
        with (
            patch.object(main, "db", return_value=database),
            patch.object(main, "get_sales_order_data", return_value=sales_orders),
        ):
            result = main.home_summary_range(
                FakeRequest(),
                start_date="2026-10-05",
                end_date="2026-10-07",
            )

        self.assertEqual(result["summary_report"], {"so": 900.0, "actual": 800.0})
        self.assertEqual([day["actual"] for day in result["days"]], [100.0, 300.0, 400.0])
        self.assertEqual(result["days"][0]["so"], 200.0)
        self.assertEqual(result["month_summary"]["actual"], 800.0)

    def test_home_summary_builds_daily_weekly_monthly_and_yearly_totals(self):
        with (
            patch.object(main, "db", return_value=MemoryHomeSummary()),
            patch.object(main, "get_sales_order_data", return_value={}),
        ):
            result = main.home_summary(FakeRequest(), month="2026-10")

        self.assertEqual(len(result["days"]), 31)
        self.assertFalse(result["days"][0]["has_data"])
        self.assertTrue(result["days"][4]["has_data"])
        self.assertEqual(result["days"][5]["customers"], 2)
        self.assertEqual(len(result["weeks"]), 5)
        self.assertEqual(result["weeks"][1]["customers"], 2)
        self.assertEqual(result["month_summary"]["so"], 250)
        self.assertEqual(result["month_summary"]["actual"], 230)
        self.assertEqual(result["month_summary"]["customers"], 2)
        self.assertEqual(result["month_summary"]["operators"]["SETU"]["customers"], 1)
        self.assertEqual(result["month_summary"]["operators"]["OFF"]["customers"], 0)
        self.assertEqual(result["year_summary"]["customers"], 2)
        self.assertEqual(len(result["year_months"]), 10)
        self.assertEqual(result["year_months"][-1]["month"], "2026-10")
        self.assertEqual(result["month_summary"]["manual_so"], 1250)

    def test_home_summary_preserves_imported_days_and_forecasts_without_actual_import(self):
        sales_orders = {
            "2026-10-06": [{"customer": "SETU Customer", "so": 500}],
            "2026-10-08": [{"customer": "KHT Customer", "so": 40}],
        }
        with (
            patch.object(main, "db", return_value=MemoryHomeSummary()),
            patch.object(main, "get_sales_order_data", return_value=sales_orders),
        ):
            result = main.home_summary(FakeRequest(), month="2026-10")

        self.assertEqual(result["month_summary"]["so"], 290)
        self.assertEqual(result["month_summary"]["actual"], 270)
        self.assertEqual(result["days"][5]["so"], 100)
        self.assertEqual(result["days"][5]["actual"], 110)
        self.assertEqual(result["days"][7]["actual"], 40)

    def test_home_summary_preserves_zero_actual_from_import_and_forecasts_only_unimported_day(self):
        database = MemoryHomeSummary(
            sales_rows=[
                {
                    "report_date": date(2026, 10, 9),
                    "customer_name": "SETU Customer",
                    "operator": "SETU",
                    "customer_key": "setu-a",
                    "so": 200,
                    "actual": 0,
                    "source_file": "daily-sales.xlsx",
                },
                {
                    "report_date": date(2026, 10, 10),
                    "customer_name": "KHT Customer",
                    "operator": "KHT",
                    "customer_key": "kht-a",
                    "so": 150,
                    "actual": 12,
                    "source_file": "planner.xlsx",
                },
            ],
            actual_imported_dates=("2026-10-09",),
        )
        sales_orders = {
            "2026-10-09": [{"customer": "SETU Customer", "so": 900}],
            "2026-10-10": [{"customer": "KHT Customer", "so": 300}],
            "2026-10-11": [{"customer": "KHT Customer", "so": 400}],
        }
        with (
            patch.object(main, "db", return_value=database),
            patch.object(main, "get_sales_order_data", return_value=sales_orders),
        ):
            result = main.home_summary(FakeRequest(), month="2026-10")

        self.assertEqual(result["month_summary"]["so"], 900)
        self.assertEqual(result["month_summary"]["actual"], 700)
        self.assertEqual(result["days"][8]["so"], 200)
        self.assertEqual(result["days"][8]["actual"], 0)
        self.assertEqual(result["days"][9]["so"], 300)
        self.assertEqual(result["days"][9]["actual"], 300)
        self.assertEqual(result["days"][10]["actual"], 400)

    def test_home_summary_rejects_invalid_month(self):
        with self.assertRaises(main.HTTPException) as invalid:
            main.home_summary(FakeRequest(), month="2026-13")
        self.assertEqual(invalid.exception.status_code, 400)


class MonthlySOTargetTests(unittest.TestCase):
    def setUp(self):
        self.database = MemoryMonthlySOTargets()
        self.db_patch = patch.object(main, "db", return_value=self.database)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def test_monthly_so_is_saved_and_loaded_independently_per_month(self):
        october = asyncio.run(
            main.save_monthly_so(
                FakeRequest({"month": "2026-10", "so": 6637221.62})
            )
        )
        september = asyncio.run(
            main.save_monthly_so(
                FakeRequest({"month": "2026-09", "so": 8027252})
            )
        )

        self.assertEqual(
            main.get_monthly_so(FakeRequest(), "2026-10"),
            october,
        )
        self.assertEqual(
            main.get_monthly_so(FakeRequest(), "2026-09"),
            september,
        )
        self.assertEqual(self.database.targets["2026-10-01"]["so"], 6637221.62)
        self.assertEqual(self.database.targets["2026-09-01"]["so"], 8027252)

    def test_monthly_so_rejects_invalid_target(self):
        for target in ("not-a-number", -1, float("inf"), True):
            with self.subTest(target=target):
                with self.assertRaises(main.HTTPException) as invalid:
                    asyncio.run(
                        main.save_monthly_so(
                            FakeRequest({"month": "2026-10", "so": target})
                        )
                    )
                self.assertEqual(invalid.exception.status_code, 400)

    def test_monthly_so_requires_valid_month(self):
        with self.assertRaises(main.HTTPException) as invalid:
            main.get_monthly_so(FakeRequest(), "2026-13")
        self.assertEqual(invalid.exception.status_code, 400)


class ImportHistoryTests(unittest.TestCase):
    def test_failed_import_is_saved_for_dashboard_status(self):
        database = MemoryImportHistory()
        with patch.object(main, "db", return_value=database):
            with patch.object(
                main,
                "load_workbook",
                side_effect=ValueError(
                    "Impor dibatalkan. Operator tidak ditemukan otomatis untuk customer: Baru."
                ),
            ):
                with self.assertRaisesRegex(ValueError, "Operator tidak ditemukan otomatis"):
                    main.import_excel(Path("workbook.xlsx"), "workbook.xlsx")

        self.assertEqual(len(database.rows), 1)
        self.assertEqual(database.rows[0][0], "workbook.xlsx")
        self.assertEqual(database.rows[0][3:5], (0, "GAGAL"))
        self.assertIn("Operator tidak ditemukan otomatis", database.rows[0][5])


if __name__ == "__main__":
    unittest.main()
