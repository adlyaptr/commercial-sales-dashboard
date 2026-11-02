import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class SalesOrderForecastTests(unittest.TestCase):
    def test_parse_sales_order_sheet_with_indonesian_numbers(self):
        csv_text = (
            ",,,,,,\n"
            "REVISI,DATE,DAY,Total,CLIN,PENTAWIRA (KSO REN),KF\n"
            ",,,SO,SO,SO,SO\n"
            ",2-Nov-2026,,233.007,1.200,9.000,2.000\n"
            ',3-Nov-2026,,,"191095,3194",9.000,2.000\n'
        )

        result = main.parse_sales_order_spreadsheet(csv_text)

        self.assertEqual(
            result["2026-11-02"],
            [
                {"customer": "CLIN", "so": 1200},
                {"customer": "PENTAWIRA (KSO REN)", "so": 9000},
                {"customer": "KF", "so": 2000},
            ],
        )
        self.assertEqual(
            result["2026-11-03"][0],
            {"customer": "CLIN", "so": 191095.3194},
        )

    def test_parse_sales_order_sheet_rejects_invalid_values(self):
        csv_text = (
            "DATE,Customer A\n"
            "SO,SO\n"
            "2-Nov-2026,tidak valid\n"
        )
        with self.assertRaisesRegex(ValueError, "Nilai SO customer"):
            main.parse_sales_order_spreadsheet(csv_text)

    def test_overlay_uses_so_as_forecast_when_actual_is_not_imported(self):
        sales_rows = [{
            "report_date": "2026-11-03",
            "customer_key": "kf",
            "customer_name": "KF",
            "operator": "SETU",
            "so": 900,
            "actual": 12,
            "id": 7,
            "manual_fob": False,
        }]
        customers = [
            {"customer_key": "clin", "customer_name": "CLIN", "operator": "SETU"},
            {"customer_key": "pentawira", "customer_name": "PENTAWIRA", "operator": "KHT"},
            {"customer_key": "kf", "customer_name": "KF", "operator": "BLORA"},
        ]
        sales_orders = {
            "2026-11-01": [
                {"customer": "CLIN", "so": 750},
            ],
            "2026-11-02": [
                {"customer": "CLIN", "so": 1200},
                {"customer": "Missing Customer", "so": 50},
            ],
            "2026-11-03": [
                {"customer": "CLIN", "so": 1300},
                {"customer": "PENTAWIRA (KSO REN)", "so": 9000},
                {"customer": "KF", "so": 800},
            ],
        }

        rows, unmapped = main.overlay_sales_order_forecast(
            sales_rows,
            customers,
            sales_orders,
            date(2026, 11, 1),
            date(2026, 11, 3),
        )
        by_customer_date = {
            (row["customer_key"], row["report_date"]): row
            for row in rows
        }

        self.assertEqual(by_customer_date[("clin", "2026-11-01")]["actual"], 750)
        self.assertTrue(by_customer_date[("clin", "2026-11-01")]["actual_is_forecast"])
        self.assertEqual(by_customer_date[("clin", "2026-11-02")]["actual"], 1200)
        self.assertEqual(by_customer_date[("clin", "2026-11-02")]["so"], 1200)
        self.assertTrue(by_customer_date[("clin", "2026-11-02")]["actual_is_forecast"])
        self.assertEqual(by_customer_date[("clin", "2026-11-03")]["actual"], 1300)
        self.assertTrue(by_customer_date[("clin", "2026-11-03")]["actual_is_forecast"])
        self.assertEqual(by_customer_date[("pentawira", "2026-11-03")]["actual"], 9000)
        self.assertEqual(by_customer_date[("kf", "2026-11-03")]["actual"], 12)
        self.assertFalse(by_customer_date[("kf", "2026-11-03")]["actual_is_forecast"])
        self.assertEqual(unmapped, ["Missing Customer"])


if __name__ == "__main__":
    unittest.main()
