import asyncio
import os
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class FakeRequest:
    def __init__(self, payload=None, authenticated=True):
        self.payload = payload or {}
        self.session = {"username": main.APP_USERNAME} if authenticated else {}

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

        if statement.startswith("SELECT status,status_changed_at FROM complaints WHERE id="):
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
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        normalized_statement = statement.strip()
        if normalized_statement.startswith("SELECT c.customer_name, c.operator, s.so, s.actual"):
            return SimpleNamespace(fetchall=lambda: [
                {"customer_name": "Pelanggan Setu", "operator": "SETU", "so": 100, "actual": 120},
                {"customer_name": "Pelanggan KHT", "operator": "KHT", "so": 0, "actual": 10},
                {"customer_name": "Pelanggan OFF", "operator": "OFF", "so": 50, "actual": 20},
            ])

        if "AS period_start" in normalized_statement:
            return SimpleNamespace(fetchall=lambda: [
                {"period_start": date(2026, 1, 1), "so": 500, "actual": 450},
                {"period_start": date(2026, 10, 1), "so": 150, "actual": 150},
            ])

        if normalized_statement.startswith("SELECT filename, imported_at FROM import_history"):
            return SimpleNamespace(fetchone=lambda: None)

        raise AssertionError(f"Unexpected SQL in test: {statement}")


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
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if statement.startswith("SELECT so FROM monthly_so_targets"):
            return SimpleNamespace(fetchone=lambda: {"so": 1250})
        if "SELECT s.report_date, c.operator, s.customer_key, s.so, s.actual" not in statement:
            raise AssertionError(f"Unexpected SQL in test: {statement}")
        if parameters != ("2026-01-01", "2026-10-31"):
            raise AssertionError(f"Unexpected home-summary date range: {parameters}")
        return SimpleNamespace(fetchall=lambda: [
            {"report_date": date(2026, 10, 5), "operator": "SETU", "customer_key": "setu-a", "so": 100, "actual": 80},
            {"report_date": date(2026, 10, 6), "operator": "SETU", "customer_key": "setu-a", "so": 100, "actual": 90},
            {"report_date": date(2026, 10, 6), "operator": "KHT", "customer_key": "kht-a", "so": 0, "actual": 20},
            {"report_date": date(2026, 10, 7), "operator": "OFF", "customer_key": "off-a", "so": 50, "actual": 40},
        ])


class MemoryHomeSummaryRange:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if "SELECT s.report_date,c.operator,s.customer_key,s.so,s.actual" in statement:
            return SimpleNamespace(fetchall=lambda: [
                {"report_date": date(2026, 8, 5), "operator": "SETU", "customer_key": "setu-a", "so": 100, "actual": 80},
                {"report_date": date(2026, 10, 5), "operator": "SETU", "customer_key": "setu-a", "so": 200, "actual": 180},
            ])
        if statement.startswith("SELECT month_start,so FROM monthly_so_targets"):
            return SimpleNamespace(fetchall=lambda: [
                {"month_start": date(2026, 8, 1), "so": 500},
                {"month_start": date(2026, 9, 1), "so": 600},
                {"month_start": date(2026, 10, 1), "so": 700},
            ])
        if statement.startswith("SELECT SUM(so) AS total_so,SUM(actual) AS total_actual FROM sales"):
            if parameters != ("2026-08-01", "2026-11-01"):
                raise AssertionError(f"Unexpected summary-report date range: {parameters}")
            return SimpleNamespace(fetchone=lambda: {"total_so": 1800, "total_actual": 1650})
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
            FakeRequest(self.complaint(summary="Keluhan selesai", status="Closed")),
        ))
        self.assertEqual(updated["summary"], "Keluhan selesai")
        self.assertEqual(updated["status"], "Closed")

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
                FakeRequest(self.complaint(status="Closed")),
            ))
            closed_edit = asyncio.run(main.update_complaint(
                created["id"],
                FakeRequest(self.complaint(status="Closed", summary="Sudah ditutup")),
            ))
            reopened = asyncio.run(main.update_complaint(
                created["id"],
                FakeRequest(self.complaint(status="Open")),
            ))
            closed_again = asyncio.run(main.update_complaint(
                created["id"],
                FakeRequest(self.complaint(status="Closed")),
            ))

        self.assertIsNone(created["statusChangedAt"])
        self.assertIsNone(unchanged_status["statusChangedAt"])
        self.assertEqual(monitoring["status"], "Monitoring")
        self.assertIsNone(monitoring["statusChangedAt"])
        self.assertEqual(closed["status"], "Closed")
        self.assertEqual(closed_edit["statusChangedAt"], closed["statusChangedAt"])
        self.assertEqual(reopened["status"], "Open")
        self.assertIsNone(reopened["statusChangedAt"])
        self.assertNotEqual(closed_again["statusChangedAt"], closed["statusChangedAt"])

    def test_invalid_input_and_unauthenticated_access_are_rejected(self):
        with self.assertRaises(main.HTTPException) as invalid:
            asyncio.run(main.create_complaint(FakeRequest(self.complaint(date="tanggal"))))
        self.assertEqual(invalid.exception.status_code, 400)

        with self.assertRaises(main.HTTPException) as invalid_status:
            asyncio.run(main.create_complaint(FakeRequest(self.complaint(status="Resolved"))))
        self.assertEqual(invalid_status.exception.status_code, 400)

        with self.assertRaises(main.HTTPException) as unauthenticated:
            main.list_complaints(FakeRequest(authenticated=False))
        self.assertEqual(unauthenticated.exception.status_code, 401)

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


class HomeSummaryTests(unittest.TestCase):
    def test_home_summary_range_includes_monthly_targets(self):
        with patch.object(main, "db", return_value=MemoryHomeSummaryRange()):
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
        self.assertEqual(result["summary_report"], {"so": 1800, "actual": 1650})

    def test_home_summary_builds_daily_weekly_monthly_and_yearly_totals(self):
        with patch.object(main, "db", return_value=MemoryHomeSummary()):
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
