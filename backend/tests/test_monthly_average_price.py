import asyncio
import io
import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class FakeRequest:
    def __init__(self, payload=None):
        self.session = {"username": main.APP_USERNAME}
        self.payload = payload or {}

    async def json(self):
        return self.payload


class MemoryMonthlyAveragePrice:
    def __init__(
        self,
        price_unit="USD_MMBTU",
        price_usd=1,
        price_rp=0,
        rupiah_multiplier=None,
        price_active=True,
        include_in_summary=True,
        region="JAWA BARAT",
        customer_name="Customer Contoh",
        month="2026-10",
        customer_key="customer-1",
    ):
        self.price_unit = price_unit
        self.price_usd = price_usd
        self.price_rp = price_rp
        self.rupiah_multiplier = rupiah_multiplier
        self.price_active = price_active
        self.include_in_summary = include_in_summary
        self.region = region
        self.customer_name = customer_name
        self.month = month
        self.customer_key = customer_key

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if "LEFT JOIN sales s" in statement:
            self.assert_month_range(parameters)
            return SimpleNamespace(fetchall=lambda: [{
                "customer_key": self.customer_key,
                "customer_name": self.customer_name,
                "operator": "SETU",
                "so_sm3": 50000,
                "actual_sm3": 28095,
                "region": self.region,
                "price_unit": self.price_unit,
                "price_usd_per_mmbtu": self.price_usd,
                "price_rp_per_sm3": self.price_rp,
                "rupiah_multiplier": self.rupiah_multiplier,
                "price_active": self.price_active,
                "sm3_override": None,
                "mmbtu_override": None,
                "total_usd_override": None,
                "rupiah_override": None,
                "include_in_summary": self.include_in_summary,
                "sm3_per_mmbtu": 29.3078,
            }])
        if statement.startswith("SELECT exchange_rate"):
            return SimpleNamespace(fetchone=lambda: {"exchange_rate": 17895})
        if statement.startswith("SELECT operator,sm3_per_mmbtu"):
            return SimpleNamespace(fetchall=lambda: [
                {"operator": "SETU", "sm3_per_mmbtu": 29.3078},
            ])
        if statement.startswith("SELECT region,target_price_rp_sm3"):
            return SimpleNamespace(fetchall=lambda: [
                {"region": "JAWA BARAT", "target_price_rp_sm3": 8250},
            ])
        if statement.startswith("SELECT customer_keys_json"):
            return SimpleNamespace(fetchone=lambda: None)
        raise AssertionError(f"Unexpected SQL in monthly Average Price test: {statement}")

    def assert_month_range(self, parameters):
        month_start = date.fromisoformat(f"{self.month}-01")
        next_month = (
            date(month_start.year + 1, 1, 1)
            if month_start.month == 12
            else date(month_start.year, month_start.month + 1, 1)
        )
        expected = (
            month_start.isoformat(),
            next_month.isoformat(),
            month_start.isoformat(),
            month_start.isoformat(),
        )
        if parameters != expected:
            raise AssertionError(f"Unexpected month parameters: {parameters}")


class MemoryMonthlyAveragePriceWrites:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if statement.startswith("SELECT customer_key FROM customers"):
            return SimpleNamespace(fetchone=lambda: {"customer_key": parameters[0]})
        if statement.startswith("INSERT INTO monthly_average_price_"):
            self.statements.append((statement, parameters))
            return SimpleNamespace(rowcount=1)
        raise AssertionError(f"Unexpected SQL in monthly Average Price save test: {statement}")


class MemoryCustomerMappings:
    def __init__(self):
        self.customers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if statement.startswith("SELECT customer_key,operator FROM customers"):
            customer = self.customers.get(parameters[0])
            return SimpleNamespace(fetchone=lambda: customer)
        if statement.startswith("INSERT INTO customers"):
            customer_key, customer_name, operator = parameters
            self.customers[customer_key] = {
                "customer_key": customer_key,
                "customer_name": customer_name,
                "operator": operator,
            }
            return SimpleNamespace(rowcount=1)
        raise AssertionError(f"Unexpected SQL in customer mapping test: {statement}")


class MemoryAveragePriceSheetSync:
    def __init__(self):
        self.customers = [
            {"customer_key": "optima", "customer_name": "OPTIMA", "operator": "SETU"},
            {"customer_key": "clin", "customer_name": "CLIN", "operator": "SETU"},
        ]
        self.price_inputs = []
        self.existing_price_inputs = {}
        self.sales_actual = {}
        self.legacy_workbook = False
        self.legacy_cleanup = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if statement.startswith("SELECT customer_key,customer_name,operator FROM customers"):
            return SimpleNamespace(fetchall=lambda: list(self.customers))
        if statement.startswith("SELECT customer_key,operator FROM customers WHERE customer_key"):
            customer = next(
                (item for item in self.customers if item["customer_key"] == parameters[0]),
                None,
            )
            return SimpleNamespace(fetchone=lambda: customer)
        if statement.startswith("SELECT price_usd_per_mmbtu FROM monthly_average_price_inputs"):
            return SimpleNamespace(
                fetchone=lambda: self.existing_price_inputs.get(parameters[1])
            )
        if statement.startswith("SELECT COALESCE(SUM(actual),0) AS actual_sm3 FROM sales"):
            return SimpleNamespace(
                fetchone=lambda: {"actual_sm3": self.sales_actual.get(parameters[0], 0)}
            )
        if statement.startswith("SELECT month_start FROM monthly_average_price_workbook_imports"):
            return SimpleNamespace(
                fetchone=lambda: {"month_start": parameters[0]} if self.legacy_workbook else None
            )
        if statement.startswith("UPDATE monthly_average_price_inputs SET sm3_override=NULL"):
            self.legacy_cleanup.append(("clear", parameters))
            return SimpleNamespace(rowcount=1)
        if statement.startswith("DELETE FROM monthly_average_price_workbook_imports"):
            self.legacy_cleanup.append(("delete", parameters))
            return SimpleNamespace(rowcount=1)
        if statement.startswith("INSERT INTO customers"):
            key, name, operator = parameters
            customer = {"customer_key": key, "customer_name": name, "operator": operator}
            self.customers.append(customer)
            return SimpleNamespace(rowcount=1)
        if statement.startswith("INSERT INTO monthly_average_price_inputs"):
            self.price_inputs.append((statement, parameters))
            return SimpleNamespace(rowcount=1)
        raise AssertionError(f"Unexpected SQL in Average Price sheet sync test: {statement}")


class MemoryMonthlyAveragePriceWorkbookImport:
    def __init__(self):
        self.customers = [{
            "customer_key": "clin",
            "customer_name": "CLIN",
            "operator": "SETU",
        }]
        self.writes = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if statement.startswith("SELECT customer_key,customer_name,operator FROM customers"):
            return SimpleNamespace(fetchall=lambda: self.customers)
        if statement.startswith("DELETE FROM monthly_average_price_inputs"):
            self.writes.append(("delete", parameters))
            return SimpleNamespace(rowcount=1)
        if statement.startswith("INSERT INTO monthly_average_price_"):
            self.writes.append((statement, parameters))
            return SimpleNamespace(rowcount=1)
        raise AssertionError(f"Unexpected SQL in Average Price workbook import test: {statement}")


class FakeUploadFile:
    def __init__(self, filename, content):
        self.filename = filename
        self.content = content

    async def read(self):
        return self.content


class MonthlyAveragePriceTests(unittest.TestCase):
    def test_calculates_monthly_sm3_mmbtu_usd_and_rupiah(self):
        with patch.object(main, "db", return_value=MemoryMonthlyAveragePrice()):
            report = main.monthly_average_price(FakeRequest(), "2026-10")

        row = report["rows"][0]
        expected_sm3 = 28095
        expected_mmbtu = expected_sm3 / 29.3078
        expected_usd = expected_mmbtu * 1
        expected_rupiah = expected_usd * 17895
        self.assertEqual(row["sm3"], expected_sm3)
        self.assertEqual(row["so_sm3"], 50000)
        self.assertEqual(row["actual_sm3"], expected_sm3)
        self.assertTrue(row["has_valid_price"])
        self.assertAlmostEqual(row["volume_mmbtu"], expected_mmbtu)
        self.assertAlmostEqual(row["total_usd"], expected_usd)
        self.assertAlmostEqual(row["rupiah"], expected_rupiah)
        self.assertEqual(report["operator_factors"]["SETU"], 29.3078)
        self.assertEqual(report["targets"]["JAWA BARAT"], 8250)
        self.assertEqual(report["totals"]["sm3"], expected_sm3)
        self.assertAlmostEqual(
            report["totals"]["average_price_rp_sm3"],
            expected_rupiah / expected_sm3,
        )

    def test_matches_excel_calculation_with_full_precision_factor(self):
        class PreciseExcelInputs(MemoryMonthlyAveragePrice):
            def execute(self, statement, parameters=None):
                result = super().execute(statement, parameters)
                if "LEFT JOIN sales s" in statement:
                    row = result.fetchall()[0]
                    row.update({
                        "actual_sm3": 33153.46999999974,
                        "sm3_per_mmbtu": 29.307844459859,
                        "price_usd_per_mmbtu": 14.15,
                    })
                    return SimpleNamespace(fetchall=lambda: [row])
                if statement.startswith("SELECT exchange_rate"):
                    return SimpleNamespace(fetchone=lambda: {"exchange_rate": 17965})
                if statement.startswith("SELECT operator,sm3_per_mmbtu"):
                    return SimpleNamespace(fetchall=lambda: [{
                        "operator": "SETU",
                        "sm3_per_mmbtu": 29.307844459859,
                    }])
                return result

        with patch.object(
            main,
            "db",
            return_value=PreciseExcelInputs(month="2026-09"),
        ):
            report = main.monthly_average_price(FakeRequest(), "2026-09")

        row = report["rows"][0]
        self.assertAlmostEqual(row["sm3"], 33153.46999999974)
        self.assertAlmostEqual(row["volume_mmbtu"], 1131.214888403268)
        self.assertAlmostEqual(row["total_usd"], 16006.690670906244)
        self.assertAlmostEqual(row["rupiah"], 287560197.90283066)

    def test_excludes_east_java_from_consolidated_totals_from_september(self):
        with patch.object(
            main,
            "db",
            return_value=MemoryMonthlyAveragePrice(region="JAWA TIMUR"),
        ):
            report = main.monthly_average_price(FakeRequest(), "2026-10")

        self.assertEqual(len(report["rows"]), 1)
        self.assertFalse(report["rows"][0]["include_in_summary"])
        self.assertEqual(report["totals"]["sm3"], 0)
        self.assertEqual(report["totals"]["rupiah"], 0)

    def test_excludes_ksn_ranca_from_june_consolidated_totals(self):
        with patch.object(
            main,
            "db",
            return_value=MemoryMonthlyAveragePrice(
                customer_name="KSN Ranca",
                month="2026-06",
            ),
        ):
            report = main.monthly_average_price(FakeRequest(), "2026-06")

        self.assertFalse(report["rows"][0]["include_in_summary"])
        self.assertEqual(report["totals"]["sm3"], 0)
        self.assertEqual(report["totals"]["rupiah"], 0)

    def test_calculates_rupiah_priced_customers_per_sm3(self):
        with patch.object(
            main,
            "db",
            return_value=MemoryMonthlyAveragePrice(
                price_unit="IDR_SM3",
                price_usd=0,
                price_rp=8725,
            ),
        ):
            report = main.monthly_average_price(FakeRequest(), "2026-10")

        row = report["rows"][0]
        expected_rupiah = row["sm3"] * 8725
        self.assertEqual(row["price_unit"], "IDR_SM3")
        self.assertEqual(row["price_rp_per_sm3"], 8725)
        self.assertAlmostEqual(row["rupiah"], expected_rupiah)
        self.assertAlmostEqual(row["total_usd"], expected_rupiah / 17895)

    def test_july_bi_surcharge_uses_active_spreadsheet_price(self):
        with patch.object(
            main,
            "db",
            return_value=MemoryMonthlyAveragePrice(
                price_active=True,
                price_usd=15.5,
                customer_key="bisurcharge",
                customer_name="BI Surcharge",
                month="2026-07",
            ),
        ):
            report = main.monthly_average_price(FakeRequest(), "2026-07")

        row = report["rows"][0]
        self.assertEqual(row["actual_sm3"], 28095)
        self.assertEqual(row["sm3"], 28095)
        self.assertEqual(row["price_usd_per_mmbtu"], 15.5)
        self.assertTrue(row["price_active"])
        self.assertTrue(row["has_valid_price"])
        self.assertAlmostEqual(row["volume_mmbtu"], 28095 / 29.3078)
        self.assertAlmostEqual(row["total_usd"], (28095 / 29.3078) * 15.5)

    def test_sheet_sync_imports_july_bi_surcharge_price_as_active(self):
        database = MemoryAveragePriceSheetSync()
        database.customers.append({
            "customer_key": "bisurcharge",
            "customer_name": "BI Surcharge",
            "operator": "SETU",
        })
        imported = {
            "source": "Harga Customer 2026",
            "entries": [{
                "customer": "BI Surcharge",
                "price_unit": "USD_MMBTU",
                "price": 15.5,
                "active": True,
            }],
        }
        with (
            patch.object(main, "import_monthly_average_price_sheet", return_value=imported),
            patch.object(main, "db", return_value=database),
        ):
            result = asyncio.run(main.sync_monthly_average_price_sheet(
                FakeRequest({"month": "2026-07", "customer_mappings": []})
            ))

        self.assertEqual(result["deactivated"], 0)
        parameters = database.price_inputs[0][1]
        self.assertEqual(parameters[1], "bisurcharge")
        self.assertEqual(parameters[3:6], ("USD_MMBTU", 15.5, 0))
        self.assertTrue(parameters[7])

    def test_sheet_sync_turns_bi_surcharge_off_from_september(self):
        database = MemoryAveragePriceSheetSync()
        database.customers.append({
            "customer_key": "bisurcharge",
            "customer_name": "BI Surcharge",
            "operator": "SETU",
        })
        imported = {
            "source": "Harga Customer 2026",
            "entries": [{
                "customer": "BI Surcharge",
                "price_unit": "USD_MMBTU",
                "price": 0,
                "active": False,
            }],
        }
        with (
            patch.object(main, "import_monthly_average_price_sheet", return_value=imported),
            patch.object(main, "db", return_value=database),
        ):
            result = asyncio.run(main.sync_monthly_average_price_sheet(
                FakeRequest({"month": "2026-09", "customer_mappings": []})
            ))

        self.assertEqual(result["deactivated"], 1)
        parameters = database.price_inputs[0][1]
        self.assertEqual(parameters[1], "bisurcharge")
        self.assertEqual(parameters[3:6], ("USD_MMBTU", 0, 0))
        self.assertFalse(parameters[7])

    def test_bi_surcharge_sheet_price_is_active_through_august_and_off_in_september(self):
        values = [
            ["No", "Nama Customer", "USD / Rp", "Jul", "Agu", "Sep"],
            ["1", "BI Surcharge", "$ 15,50", "$ 15,50", "$ 15,50", "off"],
        ]

        july = main.parse_average_price_sheet_values(values, "2026-07")[0]
        august = main.parse_average_price_sheet_values(values, "2026-08")[0]
        september = main.parse_average_price_sheet_values(values, "2026-09")[0]

        self.assertEqual((july["price"], july["active"]), (15.5, True))
        self.assertEqual((august["price"], august["active"]), (15.5, True))
        self.assertEqual((september["price"], september["active"]), (0.0, False))

    def test_kgm_rrs_uses_normal_rupiah_per_sm3_calculation_even_with_old_multiplier(self):
        with patch.object(
            main,
            "db",
            return_value=MemoryMonthlyAveragePrice(
                price_unit="IDR_SM3",
                price_usd=0,
                price_rp=9450,
                rupiah_multiplier=9450,
                customer_key="kgmksorrs",
                customer_name="KGM (KSO RRS)",
            ),
        ):
            report = main.monthly_average_price(FakeRequest(), "2026-10")

        row = report["rows"][0]
        expected_rupiah = row["sm3"] * 9450
        base_usd = expected_rupiah / 17895
        self.assertAlmostEqual(row["total_usd"], base_usd)
        self.assertAlmostEqual(row["rupiah"], expected_rupiah)

        with patch.object(
            main,
            "db",
            return_value=MemoryMonthlyAveragePrice(
                price_unit="IDR_SM3",
                price_usd=0,
                price_rp=9450,
                rupiah_multiplier=9450,
                customer_key="clin",
                customer_name="CLIN",
            ),
        ):
            other_report = main.monthly_average_price(FakeRequest(), "2026-10")

        self.assertAlmostEqual(
            other_report["rows"][0]["rupiah"],
            other_report["rows"][0]["sm3"] * 9450,
        )

    def test_applies_pulled_rupiah_multiplier_to_winglok_ebm(self):
        class WinglokAveragePrice(MemoryMonthlyAveragePrice):
            def execute(self, statement, parameters=None):
                result = super().execute(statement, parameters)
                if "LEFT JOIN sales s" not in statement:
                    return result
                row = result.fetchall()[0]
                row.update({
                    "actual_sm3": 2264.213,
                    "sm3_per_mmbtu": 30.296696310164023,
                    "price_usd_per_mmbtu": 13.68,
                })
                return SimpleNamespace(fetchall=lambda: [row])

        with patch.object(
            main,
            "db",
            return_value=WinglokAveragePrice(
                price_usd=13.68,
                rupiah_multiplier=8225,
                customer_key="winglokksoebm",
                customer_name="WINGLOK (KSO EBM)",
            ),
        ):
            report = main.monthly_average_price(FakeRequest(), "2026-10")

        row = report["rows"][0]
        expected_usd = (2264.213 / 30.296696310164023) * 13.68
        self.assertAlmostEqual(row["total_usd"], expected_usd)
        self.assertAlmostEqual(row["rupiah"], expected_usd * 8225)

    def test_keeps_summary_excluded_customer_visible_but_out_of_totals(self):
        with patch.object(
            main,
            "db",
            return_value=MemoryMonthlyAveragePrice(include_in_summary=False),
        ):
            report = main.monthly_average_price(FakeRequest(), "2026-10")

        self.assertEqual(len(report["rows"]), 1)
        self.assertFalse(report["rows"][0]["include_in_summary"])
        self.assertTrue(report["rows"][0]["has_valid_price"])
        self.assertEqual(report["totals"]["sm3"], 0)
        self.assertEqual(report["totals"]["rupiah"], 0)

    def test_excludes_pentawira_from_monthly_average_price(self):
        with patch.object(
            main,
            "db",
            return_value=MemoryMonthlyAveragePrice(customer_key="pentawiraksoren"),
        ):
            report = main.monthly_average_price(FakeRequest(), "2026-10")

        self.assertEqual(report["rows"], [])
        self.assertEqual(report["totals"]["sm3"], 0)

    def test_rejects_pentawira_average_price_entry(self):
        payload = {
            "month": "2026-10",
            "operator_factors": {},
            "exchange_rate": 17895,
            "entries": [{
                "customer_key": "pentawiraksoren",
                "region": "JAWA TIMUR",
                "price_unit": "USD_MMBTU",
                "price_usd_per_mmbtu": 10,
            }],
            "targets": {},
        }

        with self.assertRaises(main.HTTPException) as raised:
            asyncio.run(main.save_monthly_average_price(FakeRequest(payload)))

        self.assertEqual(raised.exception.status_code, 400)

    def test_uses_imported_actual_volume_instead_of_workbook_overrides(self):
        class WorkbookAveragePrice(MemoryMonthlyAveragePrice):
            def execute(self, statement, parameters=None):
                result = super().execute(statement, parameters)
                if "LEFT JOIN sales s" not in statement:
                    return result
                row = result.fetchall()[0]
                row.update({
                    "actual_sm3": 50000,
                    "sm3_override": 1200,
                    "mmbtu_override": 42,
                    "total_usd_override": 500,
                    "rupiah_override": 8400000,
                })
                return SimpleNamespace(fetchall=lambda: [row])

        with patch.object(main, "db", return_value=WorkbookAveragePrice()):
            report = main.monthly_average_price(FakeRequest(), "2026-10")

        row = report["rows"][0]
        expected_mmbtu = 50000 / 29.3078
        self.assertEqual(row["actual_sm3"], 50000)
        self.assertEqual(row["sm3"], 50000)
        self.assertAlmostEqual(row["volume_mmbtu"], expected_mmbtu)
        self.assertAlmostEqual(row["total_usd"], expected_mmbtu)
        self.assertAlmostEqual(row["rupiah"], expected_mmbtu * 17895)
        self.assertIsNone(row["sm3_override"])
        self.assertEqual(report["totals"]["sm3"], 50000)
        self.assertAlmostEqual(report["totals"]["rupiah"], expected_mmbtu * 17895)

    def test_does_not_use_workbook_overrides_without_required_conversions(self):
        class WorkbookTotalsWithoutConversions(MemoryMonthlyAveragePrice):
            def execute(self, statement, parameters=None):
                result = super().execute(statement, parameters)
                if "LEFT JOIN sales s" not in statement:
                    if statement.startswith("SELECT exchange_rate"):
                        return SimpleNamespace(fetchone=lambda: {"exchange_rate": 0})
                    return result
                row = result.fetchall()[0]
                row.update({
                    "operator": "OFF",
                    "sm3_per_mmbtu": 0,
                    "sm3_override": 1200,
                    "mmbtu_override": 42,
                    "total_usd_override": 500,
                    "rupiah_override": 8400000,
                })
                return SimpleNamespace(fetchall=lambda: [row])

        with patch.object(main, "db", return_value=WorkbookTotalsWithoutConversions()):
            report = main.monthly_average_price(FakeRequest(), "2026-10")

        row = report["rows"][0]
        self.assertFalse(row["has_valid_price"])
        self.assertEqual(row["sm3"], 28095)
        self.assertIsNone(row["mmbtu_override"])
        self.assertEqual(report["totals"]["sm3"], 0)
        self.assertEqual(report["totals"]["mmbtu"], 0)
        self.assertEqual(report["totals"]["usd"], 0)
        self.assertEqual(report["totals"]["rupiah"], 0)

    def test_ignores_legacy_workbook_summary_and_calculates_from_live_data(self):
        class ImportedWorkbookAveragePrice(MemoryMonthlyAveragePrice):
            def execute(self, statement, parameters=None):
                if statement.startswith("SELECT customer_keys_json"):
                    return SimpleNamespace(fetchone=lambda: {
                        "filename": "Average Selling Price 2026.xlsx",
                        "imported_at": "2026-11-09T12:00:00",
                        "customer_keys_json": '["customer-1"]',
                        "summary_sm3": 1200,
                        "summary_rupiah": 9000000,
                        "summary_average_price": 7500,
                    })
                if "LEFT JOIN sales s" in statement:
                    self.assert_month_range(parameters)
                    row = super().execute(statement, parameters).fetchall()[0]
                    row.update({
                        "sm3_override": 1200,
                        "mmbtu_override": 42,
                        "total_usd_override": 500,
                        "rupiah_override": 9000000,
                        "include_in_summary": False,
                    })
                    return SimpleNamespace(fetchall=lambda: [row])
                return super().execute(statement, parameters)

        with patch.object(main, "db", return_value=ImportedWorkbookAveragePrice()):
            report = main.monthly_average_price(FakeRequest(), "2026-10")

        self.assertEqual(report["source"], "system")
        self.assertIsNone(report["workbook_import"])
        self.assertEqual(report["workbook_customer_keys"], [])
        self.assertEqual(report["rows"][0]["sm3"], 28095)
        self.assertIsNone(report["rows"][0]["sm3_override"])
        self.assertTrue(report["rows"][0]["include_in_summary"])
        self.assertEqual(report["totals"]["sm3"], 28095)
        self.assertEqual(report["totals"]["rupiah"], report["rows"][0]["rupiah"])

    def test_parses_monthly_average_price_workbook_cached_values(self):
        workbook = main.Workbook()
        worksheet = workbook.active
        worksheet.title = "AVG Jan"
        worksheet.cell(1, 1, "Januari 2026")
        worksheet.cell(1, 16, 2000)
        worksheet.cell(1, 18, 200000)
        worksheet.cell(4, 2, "CLIN")
        for column, value in enumerate((50000, 1800, 20, 36000, 450000000), start=3):
            worksheet.cell(4, column, value)
        worksheet.cell(5, 2, "Customer Rupiah")
        for column, value in enumerate((100, 0, None, 0, 100000), start=3):
            worksheet.cell(5, column, value)
        worksheet.cell(6, 2, "Kurs JISDOR")
        worksheet.cell(6, 3, 12500)
        buffer = io.BytesIO()
        workbook.save(buffer)

        parsed = main.parse_monthly_average_price_workbook(
            buffer.getvalue(),
            "Average Selling Price 2026.xlsx",
        )

        self.assertEqual(parsed["months"][0]["month"], "2026-01")
        self.assertEqual(len(parsed["months"][0]["entries"]), 2)
        self.assertEqual(parsed["months"][0]["entries"][0]["customer"], "CLIN")
        rupiah_entry = parsed["months"][0]["entries"][1]
        self.assertEqual(rupiah_entry["price_unit"], "IDR_SM3")
        self.assertEqual(rupiah_entry["price_rp_per_sm3"], 1000)
        self.assertEqual(rupiah_entry["total_usd_override"], 0)
        self.assertEqual(parsed["months"][0]["summary_sm3"], 100)
        self.assertEqual(parsed["months"][0]["summary_rupiah"], 200000)

    def test_imports_legacy_workbook_rows_for_compatibility(self):
        database = MemoryMonthlyAveragePriceWorkbookImport()
        parsed = {
            "filename": "Average Selling Price 2026.xlsx",
            "months": [{
                "month": "2026-01",
                "entries": [{
                    "customer": "CLIN",
                    "region": "JAWA BARAT",
                    "price_unit": "USD_MMBTU",
                    "price_usd_per_mmbtu": 20,
                    "price_rp_per_sm3": 0,
                    "sm3_override": 50000,
                    "mmbtu_override": 1800,
                    "total_usd_override": 36000,
                    "rupiah_override": 450000000,
                    "include_in_summary": True,
                }],
                "exchange_rate": 12500,
                "summary_sm3": 50000,
                "summary_rupiah": 450000000,
                "summary_average_price": 9000,
            }],
        }
        with (
            patch.object(main, "parse_monthly_average_price_workbook", return_value=parsed),
            patch.object(main, "db", return_value=database),
        ):
            result = asyncio.run(main.import_monthly_average_price_workbook(
                FakeRequest(),
                FakeUploadFile("Average Selling Price 2026.xlsx", b"workbook"),
            ))

        self.assertEqual(result["imported_rows"], 1)
        self.assertEqual(result["imported_months"][0]["month"], "2026-01")
        input_write = next(
            write for write in database.writes
            if write[0].startswith("INSERT INTO monthly_average_price_inputs")
        )
        self.assertEqual(input_write[1][1:5], ("clin", "JAWA BARAT", "USD_MMBTU", 20))
        self.assertEqual(input_write[1][6:10], (50000, 1800, 36000, 450000000))

    def test_google_sheet_sync_clears_legacy_workbook_overrides(self):
        database = MemoryAveragePriceSheetSync()
        database.legacy_workbook = True
        request = FakeRequest({"month": "2026-01", "customer_mappings": []})
        imported = {"source": "Harga Customer 2026", "entries": []}
        with (
            patch.object(main, "db", return_value=database),
            patch.object(
                main, "import_monthly_average_price_sheet", return_value=imported,
            ),
        ):
            result = asyncio.run(main.sync_monthly_average_price_sheet(request))

        self.assertNotIn("workbook_locked", result)
        self.assertEqual(result["source"], "Harga Customer 2026")
        self.assertEqual(
            database.legacy_cleanup,
            [
                ("clear", ("2026-01-01",)),
                ("delete", ("2026-01-01",)),
            ],
        )

    def test_saves_monthly_factors_exchange_rate_and_customer_price(self):
        database = MemoryMonthlyAveragePriceWrites()
        payload = {
            "month": "2026-10",
            "operator_factors": {
                "SETU": 29.307844459859,
                "KHT": 29.3,
                "BLORA": 29.4,
                "WUNUT": 29.5,
            },
            "exchange_rate": 17895,
            "entries": [{
                "customer_key": "customer-1",
                "region": "JAWA BARAT",
                "price_unit": "USD_MMBTU",
                "price_usd_per_mmbtu": 1,
                "include_in_summary": False,
            }],
            "targets": {"JAWA BARAT": 8249.908607122522},
        }
        with patch.object(main, "db", return_value=database):
            result = asyncio.run(main.save_monthly_average_price(FakeRequest(payload)))

        self.assertEqual(result, {"ok": True, "saved": 1})
        self.assertEqual(len(database.statements), 7)
        factor_insert = next(
            parameters for statement, parameters in database.statements
            if statement.startswith("INSERT INTO monthly_average_price_operator_factors")
        )
        self.assertEqual(factor_insert[:3], ("2026-10-01", "SETU", 29.307844459859))
        price_insert = next(
            parameters for statement, parameters in database.statements
            if statement.startswith("INSERT INTO monthly_average_price_inputs")
        )
        self.assertEqual(
            price_insert[:6],
            ("2026-10-01", "customer-1", "JAWA BARAT", "USD_MMBTU", 1.0, 0.0),
        )
        self.assertTrue(price_insert[7])
        self.assertIsNone(price_insert[6])
        self.assertTrue(price_insert[7])
        self.assertEqual(price_insert[8:12], (None, None, None, None))
        self.assertFalse(price_insert[12])
        self.assertIsInstance(price_insert[13], str)
        target_insert = next(
            parameters for statement, parameters in database.statements
            if statement.startswith("INSERT INTO monthly_average_price_targets")
        )
        self.assertEqual(target_insert[:3], ("2026-10-01", "JAWA BARAT", 8250))

    def test_saves_rupiah_price_per_sm3(self):
        database = MemoryMonthlyAveragePriceWrites()
        payload = {
            "month": "2026-10",
            "operator_factors": {},
            "exchange_rate": 17917,
            "entries": [{
                "customer_key": "customer-1",
                "region": "JAWA BARAT",
                "price_unit": "IDR_SM3",
                "price_rp_per_sm3": 8725,
                "price_active": True,
            }],
            "targets": {},
        }
        with patch.object(main, "db", return_value=database):
            asyncio.run(main.save_monthly_average_price(FakeRequest(payload)))

        price_insert = next(
            parameters for statement, parameters in database.statements
            if statement.startswith("INSERT INTO monthly_average_price_inputs")
        )
        self.assertEqual(
            price_insert[:6],
            ("2026-10-01", "customer-1", "JAWA BARAT", "IDR_SM3", 0.0, 8725.0),
        )
        self.assertTrue(price_insert[7])

    def test_july_bi_surcharge_can_be_saved_with_active_spreadsheet_price(self):
        database = MemoryMonthlyAveragePriceWrites()
        payload = {
            "month": "2026-07",
            "operator_factors": {},
            "exchange_rate": 17917,
            "entries": [{
                "customer_key": "bisurcharge",
                "price_unit": "USD_MMBTU",
                "price_usd_per_mmbtu": 15.5,
                "price_active": True,
            }],
            "targets": {},
        }
        with patch.object(main, "db", return_value=database):
            asyncio.run(main.save_monthly_average_price(FakeRequest(payload)))

        price_insert = next(
            parameters for statement, parameters in database.statements
            if statement.startswith("INSERT INTO monthly_average_price_inputs")
        )
        self.assertEqual(price_insert[4], 15.5)
        self.assertTrue(price_insert[7])

    def test_saves_rupiah_multiplier_only_for_winglok_ebm(self):
        database = MemoryMonthlyAveragePriceWrites()
        payload = {
            "month": "2026-10",
            "operator_factors": {},
            "exchange_rate": 17917,
            "entries": [
                {
                    "customer_key": "kgmksorrs",
                    "price_unit": "IDR_SM3",
                    "price_rp_per_sm3": 9450,
                    "rupiah_multiplier": 9450,
                },
                {
                    "customer_key": "winglokksoebm",
                    "price_unit": "IDR_SM3",
                    "price_rp_per_sm3": 8225,
                    "rupiah_multiplier": 8225,
                },
                {
                    "customer_key": "clin",
                    "price_unit": "IDR_SM3",
                    "price_rp_per_sm3": 8725,
                    "rupiah_multiplier": 8725,
                },
            ],
            "targets": {},
        }
        with patch.object(main, "db", return_value=database):
            asyncio.run(main.save_monthly_average_price(FakeRequest(payload)))

        inserts = [
            parameters for statement, parameters in database.statements
            if statement.startswith("INSERT INTO monthly_average_price_inputs")
        ]
        self.assertEqual(
            {parameters[1]: parameters[6] for parameters in inserts},
            {"kgmksorrs": None, "winglokksoebm": 8225, "clin": None},
        )

    def test_saves_each_customer_once_per_month(self):
        payload = {
            "month": "2026-10",
            "operator_factors": {},
            "exchange_rate": 17895,
            "entries": [
                {"customer_key": "customer-1", "price_usd_per_mmbtu": 12},
                {"customer_key": "customer-1", "price_usd_per_mmbtu": 13},
            ],
            "targets": {},
        }
        with patch.object(main, "db", side_effect=AssertionError("database should not be accessed")):
            with self.assertRaises(main.HTTPException) as error:
                asyncio.run(main.save_monthly_average_price(FakeRequest(payload)))

        self.assertEqual(error.exception.status_code, 400)
        self.assertIn("lebih dari sekali", error.exception.detail)

    def test_customer_mapping_is_idempotent_and_returns_stable_key(self):
        database = MemoryCustomerMappings()
        payload = {"customer": "Customer Baru", "operator": "SETU"}
        with patch.object(main, "db", return_value=database):
            first = asyncio.run(main.save_mapping(FakeRequest(payload)))
            second = asyncio.run(main.save_mapping(FakeRequest(payload)))

        self.assertEqual(first, {
            "ok": True,
            "customer_key": "customerbaru",
            "created": True,
        })
        self.assertEqual(second, {
            "ok": True,
            "customer_key": "customerbaru",
            "created": False,
        })
        self.assertEqual(len(database.customers), 1)

    def test_customer_mapping_does_not_overwrite_existing_operator(self):
        database = MemoryCustomerMappings()
        database.customers["customerbaru"] = {
            "customer_key": "customerbaru",
            "customer_name": "Customer Baru",
            "operator": "SETU",
        }
        with patch.object(main, "db", return_value=database):
            with self.assertRaises(main.HTTPException) as error:
                asyncio.run(main.save_mapping(FakeRequest({
                    "customer": "Customer Baru",
                    "operator": "KHT",
                })))

        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(database.customers["customerbaru"]["operator"], "SETU")

    def test_rejects_invalid_month_before_database_access(self):
        with patch.object(main, "db", side_effect=AssertionError("database should not be accessed")):
            with self.assertRaises(main.HTTPException) as error:
                main.monthly_average_price(FakeRequest(), "2026-13")
        self.assertEqual(error.exception.status_code, 400)

    def test_parses_usd_and_rupiah_price_formats_from_sheet_cells(self):
        self.assertEqual(
            main.parse_average_price_cell("$ 14,15"),
            {"price_unit": "USD_MMBTU", "price": 14.15, "active": True},
        )
        self.assertEqual(
            main.parse_average_price_cell("Rp10.225"),
            {"price_unit": "IDR_SM3", "price": 10225, "active": True},
        )
        self.assertEqual(
            main.parse_average_price_cell("off", "$ 12,20"),
            {"price_unit": "USD_MMBTU", "price": 0.0, "active": False},
        )

    def test_parses_sheet_prices_for_selected_month_and_ignores_off_rows(self):
        values = [
            ["Harga Customer 2026"],
            ["No", "Nama Customer", "USD / Rp", "Jan", "Feb", "Mar"],
            ["1", "MKG", "$ 14,15", "$ 14,15", "$ 14,15", "$ 15,25"],
            ["2", "CLIN", "", "Rp8.725", "Rp8.725", "Rp9.000"],
            ["3", "TOMIMOTO", "$ 12,20", "$ 12,20", "$ 12,20", "off"],
        ]

        self.assertEqual(
            main.parse_average_price_sheet_values(values, "2026-03"),
            [
                {"customer": "MKG", "price_unit": "USD_MMBTU", "price": 15.25, "active": True},
                {"customer": "CLIN", "price_unit": "IDR_SM3", "price": 9000, "active": True},
                {"customer": "TOMIMOTO", "price_unit": "USD_MMBTU", "price": 0.0, "active": False},
            ],
        )

    def test_blank_month_value_is_imported_as_inactive_price(self):
        values = [
            ["No", "Nama Customer", "USD / Rp", "Jan"],
            ["1", "Customer A", "", "12,50"],
            ["2", "Customer B", "", ""],
        ]
        self.assertEqual(
            main.parse_average_price_sheet_values(values, "2026-01"),
            [
                {"customer": "Customer A", "price_unit": "USD_MMBTU", "price": 12.5, "active": True},
                {"customer": "Customer B", "price_unit": "USD_MMBTU", "price": 0.0, "active": False},
            ],
        )

    def test_sheet_import_falls_back_to_public_csv_without_service_account(self):
        credential_file = Path(__file__).with_name("missing-average-price-credentials.json")
        csv_content = (
            "No,Nama Customer,USD / Rp,Jan,Feb,Mar\n"
            "1,MKG,\"$ 14,15\",\"$ 14,15\",\"$ 14,15\",\"$ 15,25\"\n"
            "2,CLIN,,Rp8.725,Rp8.725,Rp9.000\n"
        ).encode("utf-8")
        response = io.BytesIO(csv_content)
        response.status = 200
        with (
            patch.object(main, "ISSUE_GOOGLE_SERVICE_ACCOUNT_FILE", str(credential_file)),
            patch.object(main, "urlopen", return_value=response),
        ):
            result = main.import_monthly_average_price_sheet(FakeRequest(), "2026-03")

        self.assertEqual(result["source"], "Harga Customer 2026")
        self.assertEqual(result["month"], "2026-03")
        self.assertEqual(
            result["entries"],
            [
                {"customer": "MKG", "price_unit": "USD_MMBTU", "price": 15.25, "active": True},
                {"customer": "CLIN", "price_unit": "IDR_SM3", "price": 9000, "active": True},
            ],
        )

    def test_public_sheet_fetch_reports_private_sheet_access(self):
        with patch.object(main, "urlopen", side_effect=main.URLError("Unauthorized")):
            with self.assertRaises(main.HTTPException) as error:
                main.fetch_public_average_price_sheet_values()
        self.assertEqual(error.exception.status_code, 502)

    def test_sheet_sync_updates_prices_and_registers_new_customer_mapping(self):
        database = MemoryAveragePriceSheetSync()
        imported = {
            "source": "Harga Customer 2026",
            "entries": [
                {
                    "customer": "OAJ",
                    "price_unit": "USD_MMBTU",
                    "price": 16.8,
                    "active": True,
                },
                {
                    "customer": "CLIN",
                    "price_unit": "IDR_SM3",
                    "price": 0,
                    "active": False,
                },
                {
                    "customer": "Customer Baru",
                    "price_unit": "USD_MMBTU",
                    "price": 12.5,
                    "active": True,
                },
            ],
        }
        request = FakeRequest({
            "month": "2026-03",
            "customer_mappings": [{
                "customer": "Customer Baru",
                "operator": "BLORA",
                "region": "JAWA TENGAH",
            }],
        })
        with (
            patch.object(main, "import_monthly_average_price_sheet", return_value=imported),
            patch.object(main, "db", return_value=database),
        ):
            result = asyncio.run(main.sync_monthly_average_price_sheet(request))

        self.assertEqual(result["imported"], 3)
        self.assertEqual(result["deactivated"], 1)
        self.assertEqual(result["created_customers"], ["Customer Baru"])
        self.assertEqual(result["unmatched_customers"], [])
        self.assertEqual(
            result["sheet_customer_keys"],
            ["clin", "customerbaru", "optima"],
        )
        self.assertEqual(len(database.price_inputs), 3)
        optima_row = next(row for row in database.price_inputs if row[1][1] == "optima")
        self.assertEqual(optima_row[1][3:6], ("USD_MMBTU", 16.8, 0))
        inactive_row = next(row for row in database.price_inputs if row[1][1] == "clin")
        self.assertEqual(inactive_row[1][3:6], ("IDR_SM3", 0, 0))

    def test_sheet_sync_prefers_exact_clin_master_over_its_long_name_alias(self):
        database = MemoryAveragePriceSheetSync()
        database.customers.append({
            "customer_key": "ptciptalestariideanusa",
            "customer_name": "PT Cipta Lestari Idea Nusa",
            "operator": "SETU",
        })
        imported = {
            "source": "Harga Customer 2026",
            "entries": [{
                "customer": "CLIN",
                "price_unit": "IDR_SM3",
                "price": 8725,
                "active": True,
            }],
        }
        request = FakeRequest({"month": "2026-03", "customer_mappings": []})
        with (
            patch.object(main, "import_monthly_average_price_sheet", return_value=imported),
            patch.object(main, "db", return_value=database),
        ):
            result = asyncio.run(main.sync_monthly_average_price_sheet(request))

        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["unmatched_customers"], [])
        self.assertEqual(
            result["sheet_customer_keys"],
            ["clin"],
        )
        self.assertEqual(len(database.price_inputs), 1)
        self.assertEqual(database.price_inputs[0][1][1], "clin")

    def test_sheet_sync_uses_kgm_sales_alias_with_normal_rupiah_price(self):
        database = MemoryAveragePriceSheetSync()
        database.customers.extend([
            {"customer_key": "kgm", "customer_name": "KGM", "operator": "SETU"},
            {
                "customer_key": "kgmksorrs",
                "customer_name": "KGM (KSO RRS)",
                "operator": "SETU",
            },
            {
                "customer_key": "kgmrrs",
                "customer_name": "KGM / RRS",
                "operator": "SETU",
            },
        ])
        database.sales_actual["kgmksorrs"] = 34235.89
        imported = {
            "source": "Harga Customer 2026",
            "entries": [{
                "customer": "KGM / RRS",
                "price_unit": "IDR_SM3",
                "price": 9450,
                "active": True,
            }],
        }
        with (
            patch.object(main, "import_monthly_average_price_sheet", return_value=imported),
            patch.object(main, "db", return_value=database),
        ):
            result = asyncio.run(main.sync_monthly_average_price_sheet(
                FakeRequest({"month": "2026-10", "customer_mappings": []})
            ))

        self.assertEqual(result["imported"], 1)
        parameters = database.price_inputs[0][1]
        self.assertEqual(parameters[1], "kgmksorrs")
        self.assertEqual(parameters[3:7], ("IDR_SM3", 0, 9450, None))

    def test_sheet_sync_uses_winglok_usd_price_alias_for_rupiah_multiplier(self):
        database = MemoryAveragePriceSheetSync()
        database.customers.extend([
            {
                "customer_key": "winglokebm",
                "customer_name": "Winglok / EBM",
                "operator": "SETU",
            },
            {
                "customer_key": "winglokksoebm",
                "customer_name": "WINGLOK (KSO EBM)",
                "operator": "SETU",
            },
        ])
        database.existing_price_inputs["winglokksoebm"] = {
            "price_usd_per_mmbtu": 13.68,
        }
        imported = {
            "source": "Harga Customer 2026",
            "entries": [{
                "customer": "Winglok / EBM",
                "price_unit": "IDR_SM3",
                "price": 8225,
                "active": True,
            }],
        }
        with (
            patch.object(main, "import_monthly_average_price_sheet", return_value=imported),
            patch.object(main, "db", return_value=database),
        ):
            result = asyncio.run(main.sync_monthly_average_price_sheet(
                FakeRequest({"month": "2026-10", "customer_mappings": []})
            ))

        self.assertEqual(result["imported"], 1)
        parameters = database.price_inputs[0][1]
        self.assertEqual(parameters[1], "winglokksoebm")
        self.assertEqual(parameters[3:7], (
            "USD_MMBTU", 13.68, 0, 8225,
        ))

    def test_sheet_sync_returns_unmapped_customer_for_admin_prompt(self):
        database = MemoryAveragePriceSheetSync()
        imported = {
            "source": "Harga Customer 2026",
            "entries": [{
                "customer": "Customer Baru",
                "price_unit": "USD_MMBTU",
                "price": 12.5,
                "active": True,
            }],
        }
        request = FakeRequest({"month": "2026-03", "customer_mappings": []})
        with (
            patch.object(main, "import_monthly_average_price_sheet", return_value=imported),
            patch.object(main, "db", return_value=database),
        ):
            result = asyncio.run(main.sync_monthly_average_price_sheet(request))

        self.assertEqual(result["unmatched_customers"], ["Customer Baru"])
        self.assertEqual(result["imported"], 0)
        self.assertEqual(database.price_inputs, [])

    def test_sheet_sync_matches_concord_industry_to_existing_concord_customer(self):
        database = MemoryAveragePriceSheetSync()
        database.customers.append({
            "customer_key": "concord",
            "customer_name": "Concord",
            "operator": "SETU",
        })
        imported = {
            "source": "Harga Customer 2026",
            "entries": [{
                "customer": "Concord Industry",
                "price_unit": "USD_MMBTU",
                "price": 13.25,
                "active": True,
            }],
        }
        request = FakeRequest({"month": "2026-03", "customer_mappings": []})
        with (
            patch.object(main, "import_monthly_average_price_sheet", return_value=imported),
            patch.object(main, "db", return_value=database),
        ):
            result = asyncio.run(main.sync_monthly_average_price_sheet(request))

        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["created_customers"], [])
        self.assertEqual(result["unmatched_customers"], [])
        self.assertEqual(result["sheet_customer_keys"], ["concord"])
        self.assertEqual(len(database.price_inputs), 1)
        self.assertEqual(database.price_inputs[0][1][1], "concord")


if __name__ == "__main__":
    unittest.main()
