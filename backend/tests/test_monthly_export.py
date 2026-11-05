import asyncio
import sys
import unittest
from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class MemoryMonthlyExport:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if "FROM sales s" in statement:
            if parameters != ("2026-10-01", "2026-10-31"):
                raise AssertionError(f"Unexpected export date range: {parameters}")
            return SimpleNamespace(fetchall=lambda: [
                {
                    "report_date": date(2026, 10, 5),
                    "customer_name": "Customer FOB",
                    "operator": "SETU",
                    "so": 100,
                    "actual": 120,
                },
                {
                    "report_date": date(2026, 10, 6),
                    "customer_name": "Customer KHT",
                    "operator": "KHT",
                    "so": 200,
                    "actual": 180,
                },
                {
                    "report_date": date(2026, 10, 6),
                    "customer_name": "Customer OFF",
                    "operator": "OFF",
                    "so": 50,
                    "actual": 40,
                },
            ])
        if statement.startswith("SELECT so FROM monthly_so_targets"):
            return SimpleNamespace(fetchone=lambda: {"so": 1000})
        raise AssertionError(f"Unexpected SQL in export test: {statement}")


class MonthlyExportTests(unittest.TestCase):
    def test_export_creates_requested_sheets_and_month_totals(self):
        with patch.object(main, "db", return_value=MemoryMonthlyExport()):
            response = main.export_monthly_report(
                SimpleNamespace(session={"username": main.APP_USERNAME}),
                year=2026,
                month=10,
            )

        async def read_body():
            return b"".join(
                [chunk async for chunk in response.body_iterator]
            )

        workbook_bytes = asyncio.run(read_body())
        workbook = load_workbook(BytesIO(workbook_bytes), data_only=True)
        self.assertEqual(
            workbook.sheetnames,
            [
                "Target 2026",
                "SUMMARY REPORT",
                "Weekly Summary",
                "SETU",
                "KHT",
                "BLORA",
                "WUNUT",
            ],
        )

        summary = workbook["SUMMARY REPORT"]
        self.assertEqual(summary["L6"].value, 1000)
        self.assertEqual(summary["L12"].value, 340)
        self.assertEqual(summary["L13"].value, 220)
        self.assertEqual(summary["L14"].value, 120)
        self.assertEqual(summary["L17"].value, -660)
        self.assertIsNone(summary["Q12"].value)

        weekly = workbook["Weekly Summary"]
        self.assertEqual(weekly["C1"].value, "RKAP Oktober 2026")
        self.assertEqual(weekly["D3"].value, 0)
        self.assertEqual(weekly["E3"].value, 0)
        self.assertEqual(weekly["D4"].value, 350)
        self.assertEqual(weekly["E4"].value, 340)
        self.assertEqual(weekly["C8"].value, 1000)
        self.assertEqual(weekly["D8"].value, 350)
        self.assertEqual(weekly["E8"].value, 340)

        setu = workbook["SETU"]
        customer_column = next(
            column
            for column in range(1, setu.max_column + 1)
            if setu.cell(12, column).value == "Customer FOB"
        )
        self.assertEqual(setu["A10"].value.date(), date(2026, 10, 1))
        self.assertEqual(setu.cell(20, 2).value.date(), date(2026, 10, 5))
        self.assertEqual(setu.cell(20, customer_column).value, 100)
        self.assertEqual(setu.cell(20, customer_column + 1).value, 120)
        self.assertEqual(setu["D56"].value, 100)
        self.assertEqual(setu["E56"].value, 120)
        self.assertEqual(setu["G12"].value, "CLIN")
        self.assertEqual(workbook["KHT"]["G12"].value, "IP")
        self.assertEqual(workbook["BLORA"]["G12"].value, "PA")
        self.assertEqual(workbook["WUNUT"]["G7"].value, "DJARUM")
        self.assertIn("attachment;", response.headers["content-disposition"])
        self.assertIn(".xlsx", response.headers["content-disposition"])

    def test_template_export_handles_leap_february(self):
        response = main.build_monthly_template_export(
            2024,
            2,
            [
                {
                    "report_date": date(2024, 2, 29),
                    "customer_name": "DJARUM",
                    "operator": "WUNUT",
                    "so": 50,
                    "actual": 70,
                },
            ],
            150,
        )
        workbook = load_workbook(response, data_only=True)
        wunut = workbook["WUNUT"]
        self.assertEqual(wunut["A5"].value.date(), date(2024, 2, 1))
        self.assertEqual(wunut["B45"].value.date(), date(2024, 2, 29))
        self.assertEqual(wunut["G45"].value, 50)
        self.assertEqual(wunut["H45"].value, 70)
        self.assertEqual(wunut["D51"].value, 50)
        self.assertEqual(wunut["E51"].value, 70)
        self.assertEqual(workbook["Weekly Summary"]["D7"].value, 50)

    def test_template_export_combines_sixth_calendar_week(self):
        response = main.build_monthly_template_export(
            2026,
            8,
            [
                {
                    "report_date": date(2026, 8, 31),
                    "customer_name": "Customer FOB",
                    "operator": "SETU",
                    "so": 50,
                    "actual": 70,
                },
            ],
            1000,
        )
        workbook = load_workbook(response, data_only=False)
        setu = workbook["SETU"]
        self.assertEqual(setu["B54"].value.date(), date(2026, 8, 31))
        self.assertEqual(setu["D55"].value, 50)
        self.assertEqual(setu["E55"].value, 70)
        self.assertIn("SETU!$AQ$14:$AQ$55", workbook["Weekly Summary"]["B14"].value)

        weekly = workbook["Weekly Summary"]
        self.assertEqual(weekly["A7"].value, "Sub Total Week 5-6")
        self.assertEqual(weekly["D7"].value, 50)
        self.assertEqual(weekly["E7"].value, 70)

    def test_export_rejects_invalid_month(self):
        with self.assertRaises(main.HTTPException) as invalid:
            main.export_monthly_report(
                SimpleNamespace(session={"username": main.APP_USERNAME}),
                year=2026,
                month=13,
            )

        self.assertEqual(invalid.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
