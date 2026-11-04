import json
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

    def test_parse_sales_order_gviz_response_preserves_spreadsheet_precision(self):
        response = {
            "status": "ok",
            "table": {
                "cols": [
                    {"label": "DATE", "type": "date"},
                    {"label": "Total SO", "type": "number"},
                    {"label": "CLIN SO", "type": "number"},
                    {"label": "HCI SO", "type": "number"},
                ],
                "rows": [{
                    "c": [
                        {"v": "Date(2026,10,2)"},
                        {"v": 233007.36780645157, "f": "233.007"},
                        {"v": 1199.5729032258068, "f": "1.200"},
                        {"v": 15600, "f": "15.600"},
                    ],
                }],
            },
        }
        response_text = (
            "/*O_o*/\ngoogle.visualization.Query.setResponse("
            f"{json.dumps(response)});"
        )

        result = main.parse_sales_order_gviz_response(response_text)

        self.assertEqual(
            result["2026-11-02"],
            [
                {"customer": "CLIN", "so": 1199.5729032258068},
                {"customer": "HCI", "so": 15600.0},
            ],
        )

    def test_parse_sales_order_gviz_response_rejects_invalid_customer_values(self):
        response = {
            "status": "ok",
            "table": {
                "cols": [
                    {"label": "DATE", "type": "date"},
                    {"label": "Customer A SO", "type": "number"},
                ],
                "rows": [{
                    "c": [{"v": "Date(2026,10,2)"}, {"v": "invalid"}],
                }],
            },
        }
        response_text = (
            "google.visualization.Query.setResponse("
            f"{json.dumps(response)});"
        )
        with self.assertRaisesRegex(ValueError, "Nilai SO customer"):
            main.parse_sales_order_gviz_response(response_text)

    def test_overlay_forecasts_zero_actuals_only_when_day_has_no_nonzero_actual(self):
        sales_rows = [{
            "report_date": "2026-11-03",
            "customer_key": "kf",
            "customer_name": "KF",
            "operator": "SETU",
            "so": 900,
            "actual": 12,
            "id": 7,
            "manual_fob": False,
        }, {
            "report_date": "2026-11-03",
            "customer_key": "pentawira",
            "customer_name": "PENTAWIRA",
            "operator": "KHT",
            "so": 0,
            "actual": 0,
            "id": 8,
            "manual_fob": False,
        }, {
            "report_date": "2026-11-04",
            "customer_key": "pentawira",
            "customer_name": "PENTAWIRA",
            "operator": "KHT",
            "so": 0,
            "actual": 0,
            "id": 9,
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
            "2026-11-04": [
                {"customer": "PENTAWIRA", "so": 7000},
            ],
        }

        rows, unmapped = main.overlay_sales_order_forecast(
            sales_rows,
            customers,
            sales_orders,
            date(2026, 11, 1),
            date(2026, 11, 4),
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
        self.assertEqual(by_customer_date[("pentawira", "2026-11-03")]["actual"], 0)
        self.assertFalse(by_customer_date[("pentawira", "2026-11-03")]["actual_is_forecast"])
        self.assertEqual(by_customer_date[("pentawira", "2026-11-04")]["actual"], 7000)
        self.assertTrue(by_customer_date[("pentawira", "2026-11-04")]["actual_is_forecast"])
        self.assertEqual(by_customer_date[("kf", "2026-11-03")]["actual"], 12)
        self.assertFalse(by_customer_date[("kf", "2026-11-03")]["actual_is_forecast"])
        self.assertEqual(unmapped, ["Missing Customer"])


if __name__ == "__main__":
    unittest.main()
