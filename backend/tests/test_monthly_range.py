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
        if "FROM monthly_average_price_inputs price_inputs" in statement:
            return SimpleNamespace(fetchall=lambda: [])
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
            "sm3_override": None,
            "mmbtu_override": None,
            "total_usd_override": None,
            "rupiah_override": None,
            "include_in_summary": True,
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
        expected_sm3 = 28095
        expected_mmbtu = expected_sm3 / 29.3078
        self.assertEqual(row["sm3"], expected_sm3)
        self.assertTrue(row["has_valid_price"])
        self.assertAlmostEqual(row["volume_mmbtu"], expected_mmbtu)
        self.assertAlmostEqual(row["total_usd"], expected_mmbtu)
        self.assertAlmostEqual(row["rupiah"], expected_mmbtu * 17895)
        self.assertAlmostEqual(result["totals"]["mmbtu"], expected_mmbtu)
        self.assertAlmostEqual(
            result["totals"]["average_price_rp_sm3"],
            row["rupiah"] / expected_sm3,
        )

    def test_excludes_customers_without_valid_price_from_average_totals(self):
        class IncludesUnpricedCustomer(MemoryAveragePriceRange):
            def execute(self, statement, parameters=None):
                result = super().execute(statement, parameters)
                if "FROM monthly_average_price_inputs price_inputs" in statement:
                    return result
                rows = result.fetchall()
                rows.append({
                    **rows[0],
                    "customer_key": "customer-2",
                    "customer_name": "Belum Ada Harga",
                    "actual_sm3": 100000,
                    "so_sm3": 50000,
                    "price_usd_per_mmbtu": 0,
                })
                return SimpleNamespace(fetchall=lambda: rows)

        with patch.object(main, "db", return_value=IncludesUnpricedCustomer()):
            result = main.monthly_average_price_range(
                FakeRequest(),
                "2026-10-01",
                "2026-10-31",
            )

        valid_row, unpriced_row = result["rows"]
        self.assertTrue(valid_row["has_valid_price"])
        self.assertFalse(unpriced_row["has_valid_price"])
        self.assertEqual(result["totals"]["sm3"], valid_row["sm3"])
        self.assertEqual(result["totals"]["rupiah"], valid_row["rupiah"])

    def test_keeps_summary_excluded_customer_visible_but_out_of_range_totals(self):
        class ExcludesSummaryCustomer(MemoryAveragePriceRange):
            def execute(self, statement, parameters=None):
                result = super().execute(statement, parameters)
                if "FROM monthly_average_price_inputs price_inputs" in statement:
                    return result
                rows = result.fetchall()
                rows[0]["include_in_summary"] = False
                return SimpleNamespace(fetchall=lambda: rows)

        with patch.object(main, "db", return_value=ExcludesSummaryCustomer()):
            result = main.monthly_average_price_range(
                FakeRequest(),
                "2026-10-01",
                "2026-10-31",
            )

        self.assertEqual(len(result["rows"]), 1)
        self.assertFalse(result["rows"][0]["include_in_summary"])
        self.assertEqual(result["totals"]["sm3"], 0)
        self.assertEqual(result["totals"]["rupiah"], 0)

    def test_uses_workbook_overrides_for_a_complete_month(self):
        class WorkbookAveragePriceRange(MemoryAveragePriceRange):
            def execute(self, statement, parameters=None):
                result = super().execute(statement, parameters)
                rows = result.fetchall()
                if rows:
                    rows[0].update({
                        "sm3_override": 1200,
                        "mmbtu_override": 42,
                        "total_usd_override": 500,
                        "rupiah_override": 8400000,
                    })
                return SimpleNamespace(fetchall=lambda: rows)

        with patch.object(main, "db", return_value=WorkbookAveragePriceRange()):
            result = main.monthly_average_price_range(
                FakeRequest(),
                "2026-10-01",
                "2026-10-31",
            )

        self.assertEqual(result["totals"]["sm3"], 1200)
        self.assertEqual(result["totals"]["mmbtu"], 42)
        self.assertEqual(result["totals"]["usd"], 500)
        self.assertEqual(result["totals"]["rupiah"], 8400000)

    def test_calculates_totals_from_workbook_mmbtu_when_amount_overrides_are_missing(self):
        class WorkbookMmbtuOnlyRange(MemoryAveragePriceRange):
            def execute(self, statement, parameters=None):
                result = super().execute(statement, parameters)
                rows = result.fetchall()
                if rows:
                    rows[0]["mmbtu_override"] = 42
                return SimpleNamespace(fetchall=lambda: rows)

        with patch.object(main, "db", return_value=WorkbookMmbtuOnlyRange()):
            result = main.monthly_average_price_range(
                FakeRequest(),
                "2026-10-01",
                "2026-10-31",
            )

        row = result["rows"][0]
        self.assertEqual(row["volume_mmbtu"], 42)
        self.assertEqual(row["total_usd"], 42)
        self.assertEqual(row["rupiah"], 42 * 17895)
        self.assertEqual(result["totals"]["usd"], 42)
        self.assertEqual(result["totals"]["rupiah"], 42 * 17895)

    def test_counts_workbook_totals_without_exchange_or_operator_factor(self):
        class WorkbookTotalsWithoutConversions(MemoryAveragePriceRange):
            def execute(self, statement, parameters=None):
                if "FROM monthly_average_price_inputs price_inputs" in statement:
                    return SimpleNamespace(fetchall=lambda: [])
                result = super().execute(statement, parameters)
                row = result.fetchall()[0]
                row.update({
                    "operator": "OFF",
                    "sm3_per_mmbtu": 0,
                    "exchange_rate": 0,
                    "sm3_override": 1200,
                    "mmbtu_override": 42,
                    "total_usd_override": 500,
                    "rupiah_override": 8400000,
                })
                return SimpleNamespace(fetchall=lambda: [row])

        with patch.object(main, "db", return_value=WorkbookTotalsWithoutConversions()):
            result = main.monthly_average_price_range(
                FakeRequest(),
                "2026-10-01",
                "2026-10-31",
            )

        self.assertTrue(result["rows"][0]["has_valid_price"])
        self.assertEqual(result["totals"]["sm3"], 1200)
        self.assertEqual(result["totals"]["mmbtu"], 42)
        self.assertEqual(result["totals"]["usd"], 500)
        self.assertEqual(result["totals"]["rupiah"], 8400000)

    def test_ignores_full_month_overrides_for_a_partial_date_range(self):
        class PartialWorkbookAveragePriceRange(MemoryAveragePriceRange):
            def execute(self, statement, parameters=None):
                if "FROM monthly_average_price_inputs price_inputs" in statement:
                    return SimpleNamespace(fetchall=lambda: [])
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
                    "sm3_override": 1200,
                    "mmbtu_override": 42,
                    "total_usd_override": 500,
                    "rupiah_override": 8400000,
                    "sm3_per_mmbtu": 29.3078,
                    "exchange_rate": 17895,
                }])

        with patch.object(main, "db", return_value=PartialWorkbookAveragePriceRange()):
            result = main.monthly_average_price_range(
                FakeRequest(),
                "2026-10-15",
                "2026-10-31",
            )

        self.assertEqual(result["totals"]["sm3"], 28095)
        self.assertAlmostEqual(
            result["totals"]["rupiah"],
            28095 / 29.3078 * 17895,
        )

    def test_calculates_rupiah_priced_rows_in_selected_range(self):
        class RupiahAveragePriceRange(MemoryAveragePriceRange):
            def execute(self, statement, parameters=None):
                result = super().execute(statement, parameters)
                if "FROM monthly_average_price_inputs price_inputs" in statement:
                    return result
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
