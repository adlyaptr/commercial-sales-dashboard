import asyncio
from io import BytesIO
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


def operator_sheet_workbook():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "BLORA"
    sheet.cell(12, 2, "DATE")
    sheet.cell(12, 4, "TOTAL")
    sheet.cell(12, 7, "HSK (KSO GAS)")
    for column, value in ((4, "SO"), (5, "ACTUAL"), (6, "DIFF"),
                          (7, "SO"), (8, "ACTUAL"), (9, "DIFF")):
        sheet.cell(13, column, value)
    sheet.cell(14, 2, datetime(2026, 2, 23))
    sheet.cell(14, 7, 4500)
    sheet.cell(14, 8, 3905.617)
    sheet.cell(15, 2, datetime(2026, 2, 24))
    sheet.cell(15, 7, 4500)
    return workbook


class OperatorSheetImportTests(unittest.TestCase):
    def test_future_actual_zeros_do_not_mark_date_as_imported(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Daily Sales"
        sheet.cell(3, 2, "PLATINUM")
        sheet.cell(4, 3, "TARGET")
        sheet.cell(4, 4, "ACTUAL")
        future_date = main._business_today() + timedelta(days=30)
        sheet.cell(5, 2, datetime.combine(future_date, datetime.min.time()))
        sheet.cell(5, 3, 5000)
        sheet.cell(5, 4, 0)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daily-sales.xlsx"
            workbook.save(path)
            workbook.close()
            database = MemoryImportDatabase()

            with (
                patch.object(main, "db", return_value=database),
                patch.object(main, "find_operator", return_value="WUNUT"),
                patch.object(main, "_mapping_from_operator_sheets", return_value=0),
            ):
                result = main.import_excel(
                    path,
                    path.name,
                )

        self.assertEqual(result["rows_read"], 0)
        self.assertEqual(result["rows_saved"], 1)
        actual_imports = [
            row for row in database.saved
            if "INSERT INTO daily_actual_imports" in row[0]
        ]
        self.assertEqual(actual_imports, [])

    def test_import_date_filter_leaves_other_daily_sales_dates_untouched(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Daily Sales"
        sheet.cell(3, 2, "HSK (KSO GAS)")
        sheet.cell(4, 3, "TARGET")
        sheet.cell(4, 4, "ACTUAL")
        for row_number, day, actual in (
            (5, 9, 90),
            (6, 10, 0),
            (7, 11, 110),
            (8, 12, 120),
        ):
            sheet.cell(row_number, 2, datetime(2026, 11, day))
            sheet.cell(row_number, 3, 500)
            sheet.cell(row_number, 4, actual)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daily-sales.xlsx"
            workbook.save(path)
            workbook.close()

            database = MemoryImportDatabase()
            with (
                patch.object(main, "db", return_value=database),
                patch.object(main, "find_operator", return_value="BLORA"),
                patch.object(main, "_mapping_from_operator_sheets", return_value=0),
            ):
                result = main.import_excel(
                    path,
                    path.name,
                    report_dates_filter={
                        main.date(2026, 11, 10),
                        main.date(2026, 11, 11),
                    },
                )

        sales = [
            row for row in database.saved
            if row[0].startswith("INSERT INTO sales")
        ]
        self.assertEqual(result["rows_read"], 2)
        self.assertEqual(result["rows_saved"], 2)
        self.assertEqual(
            [row[1][0] for row in sales],
            ["2026-11-10", "2026-11-11"],
        )
        self.assertEqual([row[1][3] for row in sales], [0.0, 110.0])
        actual_imports = [
            row for row in database.saved
            if "INSERT INTO daily_actual_imports" in row[0]
        ]
        self.assertEqual(
            sorted(row[1][0] for row in actual_imports),
            ["2026-11-10", "2026-11-11"],
        )

    def test_full_sheet_so_import_preserves_actuals_outside_email_date_filter(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Daily Sales"
        sheet.cell(3, 2, "PLATINUM")
        sheet.cell(4, 3, "TARGET")
        sheet.cell(4, 4, "ACTUAL")
        for row_number, day, target, actual in (
            (5, 14, 500, 321),
            (6, 15, 600, 222),
            (7, 16, 700, 333),
        ):
            sheet.cell(row_number, 2, datetime(2026, 11, day))
            sheet.cell(row_number, 3, target)
            sheet.cell(row_number, 4, actual)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daily-sales.xlsx"
            workbook.save(path)
            workbook.close()
            database = MemoryImportDatabase()
            database.existing_sales.update({
                ("2026-11-15", "platinum"): {"so": 550.0, "actual": 42.0},
                ("2026-11-16", "platinum"): {"so": 660.0, "actual": 0.0},
            })

            with (
                patch.object(main, "db", return_value=database),
                patch.object(main, "find_operator", return_value="WUNUT"),
                patch.object(main, "_mapping_from_operator_sheets", return_value=0),
            ):
                result = main.import_excel(
                    path,
                    path.name,
                    report_dates_filter={main.date(2026, 11, 14)},
                    include_all_so_targets=True,
                )

        sales = [
            row for row in database.saved
            if "INSERT INTO sales" in row[0]
        ]
        self.assertEqual(result["rows_read"], 1)
        self.assertEqual(result["rows_saved"], 3)
        self.assertEqual(
            [row[1][0] for row in sales],
            ["2026-11-14", "2026-11-15", "2026-11-16"],
        )
        self.assertEqual([row[1][2] for row in sales], [500.0, 600.0, 700.0])
        self.assertEqual([row[1][3] for row in sales], [321.0, 42.0, 0.0])
        actual_imports = [
            row for row in database.saved
            if "INSERT INTO daily_actual_imports" in row[0]
        ]
        self.assertEqual(
            [row[1][0] for row in actual_imports],
            ["2026-11-14"],
        )
        forecast_rows, _ = main.overlay_sales_order_forecast(
            [{
                "report_date": row[1][0],
                "customer_key": "platinum",
                "customer_name": "PLATINUM",
                "operator": "WUNUT",
                "so": row[1][2],
                "actual": row[1][3],
                "id": None,
                "manual_fob": False,
            } for row in sales],
            [{
                "customer_key": "platinum",
                "customer_name": "PLATINUM",
                "operator": "WUNUT",
            }],
            {},
            main.date(2026, 11, 14),
            main.date(2026, 11, 16),
        )
        forecast_by_date = {
            row["report_date"]: row for row in forecast_rows
        }
        self.assertEqual(forecast_by_date["2026-11-14"]["actual"], 321.0)
        self.assertEqual(forecast_by_date["2026-11-15"]["actual"], 42.0)
        self.assertEqual(forecast_by_date["2026-11-16"]["actual"], 700.0)
        self.assertTrue(forecast_by_date["2026-11-16"]["actual_is_forecast"])

    def test_selects_populated_duplicate_actual_column_and_skips_total_labels(self):
        workbook = operator_sheet_workbook()
        sheet = workbook["BLORA"]
        sheet.cell(12, 10, "FOB SETU - KPU")
        sheet.cell(13, 11, "ACTUAL")
        sheet.cell(12, 12, "FOB SETU - KPU")
        sheet.cell(13, 13, "ACTUAL")
        sheet.cell(12, 14, "TOTAL NON FOB")
        sheet.cell(13, 15, "ACTUAL")
        sheet.cell(14, 11, 0)
        sheet.cell(14, 13, 123.45)
        sheet.cell(14, 15, 999)

        try:
            records = main.operator_sheet_daily_sales_records(workbook)
        finally:
            workbook.close()

        kpu_records = [record for record in records if record["customer"] == "FOB SETU - KPU"]
        self.assertEqual([record["actual"] for record in kpu_records], [123.45, 0])
        self.assertNotIn("TOTAL NON FOB", {record["customer"] for record in records})

    def test_rejects_multiple_populated_duplicate_actual_columns(self):
        workbook = operator_sheet_workbook()
        sheet = workbook["BLORA"]
        sheet.cell(12, 10, "FOB SETU - KPU")
        sheet.cell(13, 11, "ACTUAL")
        sheet.cell(12, 12, "FOB SETU - KPU")
        sheet.cell(13, 13, "ACTUAL")
        sheet.cell(14, 11, 100)
        sheet.cell(14, 13, 200)

        try:
            with self.assertRaisesRegex(ValueError, "lebih dari satu kolom Actual"):
                main.operator_sheet_daily_sales_records(workbook)
        finally:
            workbook.close()

    def test_extracts_actuals_from_month_suffixed_and_ms_lain_sheets(self):
        workbook = operator_sheet_workbook()
        workbook["BLORA"].title = "KHT JUNI26"
        other_sheet = workbook.create_sheet("MS LAIN JUL26")
        other_sheet.cell(4, 2, "DATE")
        other_sheet.cell(4, 7, "PENTAWIRA (KSO REN)")
        other_sheet.cell(5, 8, "ACTUAL")
        other_sheet.cell(6, 2, datetime(2026, 7, 1))
        other_sheet.cell(6, 8, 123.45)

        try:
            records = main.operator_sheet_daily_sales_records(workbook)
        finally:
            workbook.close()

        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["operator"], "KHT")
        self.assertEqual(records[0]["customer"], "HSK (KSO GAS)")
        self.assertEqual(records[2], {
            "report_date": "2026-07-01",
            "customer": "PENTAWIRA (KSO REN)",
            "operator": "WUNUT",
            "actual": 123.45,
            "so": None,
        })

    def test_extracts_actuals_and_treats_blank_as_zero(self):
        workbook = operator_sheet_workbook()
        try:
            records = main.operator_sheet_daily_sales_records(workbook)
        finally:
            workbook.close()

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0], {
            "report_date": "2026-02-23",
            "customer": "HSK (KSO GAS)",
            "operator": "BLORA",
            "actual": 3905.617,
            "so": 4500.0,
        })
        self.assertEqual(records[1]["report_date"], "2026-02-24")
        self.assertEqual(records[1]["actual"], 0)
        self.assertEqual(records[1]["so"], 4500)

    def test_rejects_duplicate_customer_date_across_operator_sheets(self):
        workbook = operator_sheet_workbook()
        second_sheet = workbook.create_sheet("SETU")
        for row, values in ((12, (None, "DATE", None, None, None, None, "HSK (KSO GAS)")),
                            (13, (None, None, None, None, None, None, "ACTUAL")),
                            (14, (None, datetime(2026, 2, 23), None, None, None, None, 3905.617))):
            for column, value in enumerate(values, start=1):
                if value is not None:
                    second_sheet.cell(row, column, value)
        try:
            with self.assertRaisesRegex(ValueError, "muncul lebih dari satu kali"):
                main.operator_sheet_daily_sales_records(workbook)
        finally:
            workbook.close()

    def test_rejects_non_numeric_actual_instead_of_importing_zero(self):
        for value in ("n/a", "1,2,3"):
            with self.subTest(value=value):
                workbook = operator_sheet_workbook()
                workbook["BLORA"].cell(14, 8, value)
                try:
                    with self.assertRaisesRegex(ValueError, "bukan angka"):
                        main.operator_sheet_daily_sales_records(workbook)
                finally:
                    workbook.close()

    def test_import_saves_matrix_actual_and_preserves_existing_so_when_blank(self):
        workbook = operator_sheet_workbook()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "february.xlsx"
            workbook.save(path)
            workbook.close()

            database = MemoryImportDatabase()
            with (
                patch.object(main, "db", return_value=database),
                patch.object(main, "find_operator", return_value="BLORA"),
                patch.object(main, "_mapping_from_operator_sheets", return_value=0),
            ):
                result = main.import_excel(path, path.name)

        self.assertEqual(result["rows_read"], 2)
        self.assertEqual(result["rows_saved"], 2)
        sales = [row for row in database.saved if "INSERT INTO sales" in row[0]]
        self.assertEqual(sales[0][1][2:4], (4500.0, 3905.617))
        self.assertEqual(sales[1][1][2:4], (4500.0, 0))


class MemoryImportDatabase:
    def __init__(self):
        self.saved = []
        self.existing_sales = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if "SELECT so,actual FROM sales" in statement:
            existing = self.existing_sales.get(
                tuple(parameters),
                {"so": 4500.0, "actual": 0.0},
            )
            return type("Result", (), {"fetchone": lambda self: existing})()
        if "SELECT so FROM sales" in statement:
            existing = self.existing_sales.get(
                tuple(parameters),
                {"so": 4500.0},
            )
            return type("Result", (), {"fetchone": lambda self: existing})()
        self.saved.append((statement, parameters))
        return type("Result", (), {"rowcount": 0})()


class PreviewRequest:
    session = {}


class PreviewUpload:
    filename = "february.xlsx"

    def __init__(self, content):
        self.content = content

    async def read(self):
        return self.content


class PreviewDatabase:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        self.parameters = parameters
        return type("Result", (), {
            "fetchall": lambda self: [{
                "customer_key": "hskksogas",
                "customer_name": "HSK (KSO GAS)",
                "operator": "KHT",
            }],
        })()


class ImportPreviewTests(unittest.TestCase):
    def test_operator_sheet_preview_reports_dates_and_master_conflicts(self):
        workbook = operator_sheet_workbook()
        content = BytesIO()
        workbook.save(content)
        workbook.close()
        database = PreviewDatabase()

        with (
            patch.object(main, "require_admin"),
            patch.object(main, "db", return_value=database),
            patch.object(main, "load_workbook", wraps=main.load_workbook) as load_workbook,
        ):
            preview = asyncio.run(
                main.preview_import(PreviewRequest(), PreviewUpload(content.getvalue()))
            )

        self.assertFalse(load_workbook.call_args.kwargs["read_only"])
        self.assertEqual(preview["import_format"], "operator sheets")
        self.assertEqual(preview["rows_read"], 2)
        self.assertEqual(preview["start_date"], "2026-02-23")
        self.assertEqual(preview["end_date"], "2026-02-24")
        self.assertEqual(preview["customers"][0]["operator"], "KHT")
        self.assertEqual(preview["operator_conflicts"], [{
            "customer": "HSK (KSO GAS)",
            "source_operator": "BLORA",
            "system_operator": "KHT",
        }])


if __name__ == "__main__":
    unittest.main()
