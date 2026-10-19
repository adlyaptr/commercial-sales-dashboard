import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class FakeRequest:
    session = {"username": main.APP_USERNAME}


class MemoryMonthlyRange:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if "DATE_FORMAT(s.report_date" not in statement:
            raise AssertionError(f"Unexpected SQL in monthly range test: {statement}")
        if parameters != ("2025-12-15", "2026-02-10"):
            raise AssertionError(f"Unexpected date parameters: {parameters}")
        return SimpleNamespace(fetchall=lambda: [
            {
                "customer_key": "customer-1",
                "customer_name": "Customer Contoh",
                "operator": "SETU",
                "period": "2025-12",
                "total_so": 120,
                "total_actual": 100,
            },
            {
                "customer_key": "customer-1",
                "customer_name": "Customer Contoh",
                "operator": "SETU",
                "period": "2026-01",
                "total_so": 80,
                "total_actual": 75,
            },
        ])


class MemoryAveragePriceRange:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if "monthly_average_price_exchange_rates" not in statement:
            raise AssertionError(f"Unexpected SQL in Average Price range test: {statement}")
        if parameters != ("2026-10-01", "2026-10-31"):
            raise AssertionError(f"Unexpected date parameters: {parameters}")
        return SimpleNamespace(fetchall=lambda: [{
            "customer_key": "customer-1",
            "customer_name": "Customer Contoh",
            "operator": "SETU",
            "period": "2026-10",
            "so_sm3": 50000,
            "actual_sm3": 28095,
            "region": "JAWA BARAT",
            "price_unit": "USD_MMBTU",
            "price_usd_per_mmbtu": 1,
            "price_rp_per_sm3": 0,
            "sm3_per_mmbtu": 29.3078,
            "exchange_rate": 17895,
        }])


class MonthlyRangeTests(unittest.TestCase):
    def test_returns_monthly_customer_totals_for_exact_date_range(self):
        with patch.object(main, "db", return_value=MemoryMonthlyRange()):
            result = main.monthly_range_summary(
                FakeRequest(),
                "2025-12-15",
                "2026-02-10",
            )

        self.assertEqual(result["start_date"], "2025-12-15")
        self.assertEqual(result["end_date"], "2026-02-10")
        self.assertEqual(
            [(item["period"], item["so"], item["actual"]) for item in result["items"]],
            [("2025-12", 120, 100), ("2026-01", 80, 75)],
        )

    def test_rejects_reversed_date_range(self):
        with self.assertRaises(main.HTTPException) as raised:
            main.monthly_range_summary(
                FakeRequest(),
                "2026-02-10",
                "2025-12-15",
            )

        self.assertEqual(raised.exception.status_code, 400)

    def test_calculates_average_price_totals_for_the_selected_date_range(self):
        with patch.object(main, "db", return_value=MemoryAveragePriceRange()):
            result = main.monthly_average_price_range(
                FakeRequest(),
                "2026-10-01",
                "2026-10-31",
            )

        row = result["rows"][0]
        expected_sm3 = 50000 + 28095
        expected_mmbtu = expected_sm3 / 29.3078
        self.assertEqual(row["sm3"], expected_sm3)
        self.assertAlmostEqual(row["volume_mmbtu"], expected_mmbtu)
        self.assertAlmostEqual(row["total_usd"], expected_mmbtu)
        self.assertAlmostEqual(row["rupiah"], expected_mmbtu * 17895)
        self.assertAlmostEqual(result["totals"]["mmbtu"], expected_mmbtu)

    def test_calculates_rupiah_priced_rows_in_selected_range(self):
        class RupiahAveragePriceRange(MemoryAveragePriceRange):
            def execute(self, statement, parameters=None):
                result = super().execute(statement, parameters)
                rows = result.fetchall()
                rows[0]["price_unit"] = "IDR_SM3"
                rows[0]["price_usd_per_mmbtu"] = 0
                rows[0]["price_rp_per_sm3"] = 8725
                return SimpleNamespace(fetchall=lambda: rows)

        with patch.object(main, "db", return_value=RupiahAveragePriceRange()):
            result = main.monthly_average_price_range(
                FakeRequest(),
                "2026-10-01",
                "2026-10-31",
            )

        row = result["rows"][0]
        self.assertEqual(row["price_unit"], "IDR_SM3")
        self.assertAlmostEqual(row["rupiah"], row["sm3"] * 8725)
        self.assertAlmostEqual(row["total_usd"], row["rupiah"] / 17895)


if __name__ == "__main__":
    unittest.main()
