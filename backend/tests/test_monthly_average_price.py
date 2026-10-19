import asyncio
import sys
import unittest
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
    def __init__(self, price_unit="USD_MMBTU", price_usd=1, price_rp=0):
        self.price_unit = price_unit
        self.price_usd = price_usd
        self.price_rp = price_rp

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        if "FROM sales s" in statement:
            self.assert_month_range(parameters)
            return SimpleNamespace(fetchall=lambda: [{
                "customer_key": "customer-1",
                "customer_name": "Customer Contoh",
                "operator": "SETU",
                "so_sm3": 50000,
                "actual_sm3": 28095,
                "region": "JAWA BARAT",
                "price_unit": self.price_unit,
                "price_usd_per_mmbtu": self.price_usd,
                "price_rp_per_sm3": self.price_rp,
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
        raise AssertionError(f"Unexpected SQL in monthly Average Price test: {statement}")

    @staticmethod
    def assert_month_range(parameters):
        if parameters != ("2026-10-01", "2026-10-01", "2026-10-01", "2026-11-01"):
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


class MonthlyAveragePriceTests(unittest.TestCase):
    def test_calculates_monthly_sm3_mmbtu_usd_and_rupiah(self):
        with patch.object(main, "db", return_value=MemoryMonthlyAveragePrice()):
            report = main.monthly_average_price(FakeRequest(), "2026-10")

        row = report["rows"][0]
        expected_sm3 = 50000 + 28095
        expected_mmbtu = expected_sm3 / 29.3078
        expected_usd = expected_mmbtu * 1
        expected_rupiah = expected_usd * 17895
        self.assertEqual(row["sm3"], expected_sm3)
        self.assertAlmostEqual(row["volume_mmbtu"], expected_mmbtu)
        self.assertAlmostEqual(row["total_usd"], expected_usd)
        self.assertAlmostEqual(row["rupiah"], expected_rupiah)
        self.assertEqual(report["operator_factors"]["SETU"], 29.3078)
        self.assertEqual(report["targets"]["JAWA BARAT"], 8250)
        self.assertEqual(report["totals"]["sm3"], expected_sm3)

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

    def test_saves_monthly_factors_exchange_rate_and_customer_price(self):
        database = MemoryMonthlyAveragePriceWrites()
        payload = {
            "month": "2026-10",
            "operator_factors": {
                "SETU": 29.3078,
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
            }],
            "targets": {"JAWA BARAT": 8250},
        }
        with patch.object(main, "db", return_value=database):
            result = asyncio.run(main.save_monthly_average_price(FakeRequest(payload)))

        self.assertEqual(result, {"ok": True, "saved": 1})
        self.assertEqual(len(database.statements), 7)
        price_insert = next(
            parameters for statement, parameters in database.statements
            if statement.startswith("INSERT INTO monthly_average_price_inputs")
        )
        self.assertEqual(
            price_insert[:6],
            ("2026-10-01", "customer-1", "JAWA BARAT", "USD_MMBTU", 1.0, 0.0),
        )
        self.assertIsInstance(price_insert[6], str)
        target_insert = next(
            parameters for statement, parameters in database.statements
            if statement.startswith("INSERT INTO monthly_average_price_targets")
        )
        self.assertEqual(target_insert[:3], ("2026-10-01", "JAWA BARAT", 8250.0))

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

    def test_rejects_invalid_month_before_database_access(self):
        with patch.object(main, "db", side_effect=AssertionError("database should not be accessed")):
            with self.assertRaises(main.HTTPException) as error:
                main.monthly_average_price(FakeRequest(), "2026-13")
        self.assertEqual(error.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
