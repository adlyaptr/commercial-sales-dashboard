import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class BudgetSpreadsheetTests(unittest.TestCase):
    def test_parse_budget_targets_and_finance_actuals_by_month(self):
        finance_csv = (
            "PENGELUARAN\n"
            "Bulan,2026,2027\n"
            "Januari,59.229.409,\n"
            "Februari,15.637.793,\n"
            "Maret,54.488.795,\n"
            "April,9.871.380,\n"
            "Mei,62.854.798,\n"
            "Juni,6.354.673,\n"
            "Juli,65.409.203,\n"
            "Agustus,673.000,\n"
            "September,46.036.431,\n"
            "Oktober,190.000,\n"
            "November,0,\n"
            "Desember,0,\n"
            "2026\n"
            "Payment Type\n"
            "Kunjungan Rutin Existing Customer,15.878.610,5.747.183\n"
            "Canvassing,15.445.036,532.000\n"
            "Potensial Customer,1.467.400,2.728.505\n"
            "Pencarian & evaluasi sumber gas,4.974.051,766.805\n"
            "Meeting Manajemen (HO),12.518.882,3.743.000\n"
            "Area\n"
        )
        target_csv = (
            "PT Reethau\n"
            "WORK PLAN,OUTCOME,LIST COST,Account No,Account Budget Cost,PT,"
            "2026,,,,,,,,,,,,2026\n"
            "1. Sales Target 2026,Potential Customer Acquisition,"
            "1.1 Survey lokasi calon pelanggan,60,Relationship Marketing,RCE,"
            "9.350.000,9.350.000,,,,,,,,,,,112.200.000\n"
            ",,1.2 Meeting pencarian sumber gas,60,Relationship Marketing,RCE,"
            "15.000.000,15.000.000,,,,,,,,,,,180.000.000\n"
            ",,1.3 Canvassing area,60,Relationship Marketing,RCE,"
            "38.550.000,19.750.000,,,,,,,,,,,438.100.000\n"
            "2. Customer Acquisition & Retention,Customer Retention,"
            "2.1 Kunjungan rutin pelanggan,50,Customer Maintenance,RCE,"
            "31.250.000,31.250.000,,,,,,,,,,,375.000.000\n"
            "3. Marketing Support,Business Development,"
            "3.1 SPPD HO Jakarta,60,Relationship Marketing,RCE,"
            "13.000.000,13.000.000,,,,,,,,,,,155.800.000\n"
        )

        result = main.parse_budget_spreadsheets(finance_csv, target_csv)

        records = {
            (row["category"], row["month"]): row
            for row in result["records"]
        }
        self.assertEqual(len(result["records"]), 60)
        self.assertEqual(records[("Kunjungan Rutin Existing Customer", "2026-02")]["target"], 31_250_000)
        self.assertEqual(records[("Kunjungan Rutin Existing Customer", "2026-02")]["actual"], 5_747_183)
        self.assertEqual(records[("Meeting Manajemen (HO)", "2026-02")]["actual"], 3_743_000)
        self.assertEqual(records[("Canvassing", "2026-02")]["target"], 19_750_000)
        self.assertEqual(records[("Potensial", "2026-02")]["actual"], 2_728_505)
        self.assertEqual(records[("Source", "2026-02")]["actual"], 766_805)
        self.assertEqual(result["months"][0]["actual"], 59_229_409)
        self.assertEqual(result["months"][1]["actual"], 15_637_793)
        self.assertEqual(result["months"][9]["actual"], 190_000)

    def test_rejects_target_sheet_without_budget_rows(self):
        with self.assertRaisesRegex(ValueError, "target kategori"):
            main.parse_budget_spreadsheets(
                "PENGELUARAN\n"
                "Bulan,2026\n"
                "Januari,0\n"
                "Februari,0\n"
                "Maret,0\n"
                "April,0\n"
                "Mei,0\n"
                "Juni,0\n"
                "Juli,0\n"
                "Agustus,0\n"
                "September,0\n"
                "Oktober,0\n"
                "November,0\n"
                "Desember,0\n"
                "Payment Type\n",
                "WORK PLAN,OUTCOME,LIST COST,Account No,Account Budget Cost,PT,"
                "2026,,,,,,,,,,,,2026\n",
            )

    def test_budget_endpoint_requires_login(self):
        with self.assertRaises(HTTPException) as error:
            main.get_budget(SimpleNamespace(session={}))
        self.assertEqual(error.exception.status_code, 401)

    def test_budget_endpoint_returns_spreadsheet_data_for_user(self):
        request = SimpleNamespace(session={"username": "budget-admin", "role": "admin"})
        response = {"months": [], "records": [], "syncedAt": "2026-10-30T09:00:00+07:00"}
        with patch("main.get_budget_spreadsheet_data", return_value=response):
            self.assertEqual(main.get_budget(request), response)


if __name__ == "__main__":
    unittest.main()
