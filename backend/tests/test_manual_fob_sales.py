import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class FakeRequest:
    def __init__(self, payload, authenticated=True):
        self.payload = payload
        self.session = {"username": main.APP_USERNAME} if authenticated else {}

    async def json(self):
        return self.payload


class MemoryManualSales:
    def __init__(self):
        self.customers = {}
        self.sales = {}
        self.next_id = 1

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        statement = statement.strip()
        parameters = parameters or ()
        if statement.startswith("INSERT INTO customers"):
            key, customer, operator = parameters
            self.customers[key] = {"customer": customer, "operator": operator}
            return SimpleNamespace(rowcount=1)

        if "SELECT s.customer_key" in statement and "LOWER(c.customer_name)" in statement:
            report_date, operator, customer = parameters
            match = next((
                sale for sale in self.sales.values()
                if sale["report_date"] == report_date
                and sale["source_file"] == "manual-fob"
                and self.customers[sale["customer_key"]]["operator"] == operator
                and self.customers[sale["customer_key"]]["customer"].casefold() == customer.casefold()
            ), None)
            return SimpleNamespace(fetchone=lambda: {"customer_key": match["customer_key"]} if match else None)

        if statement.startswith("INSERT INTO sales"):
            report_date, customer_key, so, actual, source_file, imported_at = parameters
            sale = next((
                item for item in self.sales.values()
                if item["report_date"] == report_date and item["customer_key"] == customer_key
            ), None)
            if sale is None:
                sale = {"id": self.next_id}
                self.sales[self.next_id] = sale
                self.next_id += 1
            sale.update({
                "report_date": report_date,
                "customer_key": customer_key,
                "so": so,
                "actual": actual,
                "source_file": source_file,
                "imported_at": imported_at,
            })
            return SimpleNamespace(rowcount=1)

        if statement.startswith("SELECT s.report_date,s.customer_key"):
            sale = self.sales.get(parameters[0])
            if not sale or sale["source_file"] != "manual-fob":
                return SimpleNamespace(fetchone=lambda: None)
            return SimpleNamespace(fetchone=lambda: {
                "report_date": sale["report_date"],
                "customer_key": sale["customer_key"],
            })

        if statement.startswith("SELECT s.customer_key"):
            sale = self.sales.get(parameters[0])
            if not sale or sale["source_file"] != "manual-fob":
                return SimpleNamespace(fetchone=lambda: None)
            return SimpleNamespace(fetchone=lambda: {"customer_key": sale["customer_key"]})

        if statement.startswith("SELECT id FROM sales"):
            report_date, customer_key, sale_id = parameters
            match = next((
                sale for sale in self.sales.values()
                if sale["report_date"] == report_date
                and sale["customer_key"] == customer_key
                and sale["id"] != sale_id
            ), None)
            return SimpleNamespace(fetchone=lambda: {"id": match["id"]} if match else None)

        if statement.startswith("UPDATE sales SET"):
            customer_key, so, actual, imported_at, sale_id = parameters
            self.sales[sale_id].update({
                "customer_key": customer_key,
                "so": so,
                "actual": actual,
                "imported_at": imported_at,
            })
            return SimpleNamespace(rowcount=1)

        if statement.startswith("DELETE FROM sales WHERE id="):
            self.sales.pop(parameters[0], None)
            return SimpleNamespace(rowcount=1)

        if statement.startswith("DELETE FROM customers"):
            customer_key = parameters[0]
            if not any(sale["customer_key"] == customer_key for sale in self.sales.values()):
                self.customers.pop(customer_key, None)
            return SimpleNamespace(rowcount=1)

        raise AssertionError(f"Unexpected SQL in test: {statement}")


class ManualFobSalesTests(unittest.TestCase):
    def setUp(self):
        self.database = MemoryManualSales()

    def save(self, payload, authenticated=True):
        with patch.object(main, "db", return_value=self.database):
            return asyncio.run(main.save_manual_fob_sale(FakeRequest(payload, authenticated)))

    def update(self, sale_id, payload, authenticated=True):
        with patch.object(main, "db", return_value=self.database):
            return asyncio.run(main.update_manual_fob_sale(sale_id, FakeRequest(payload, authenticated)))

    def delete(self, sale_id, authenticated=True):
        with patch.object(main, "db", return_value=self.database):
            return main.delete_manual_fob_sale(sale_id, FakeRequest({}, authenticated=authenticated))

    def test_save_manual_fob_sale_and_update_same_date_operator_customer(self):
        first = self.save({
            "date": "2026-08-31",
            "customer": "FOB Customer A",
            "operator": "KHT",
            "so": 120,
            "actual": 90,
        })
        second = self.save({
            "date": "2026-08-31",
            "customer": "fob customer a",
            "operator": "KHT",
            "so": 100,
            "actual": 110,
        })

        self.assertEqual(first["diff"], -30)
        self.assertEqual(second["diff"], 10)
        self.assertEqual(len(self.database.sales), 1)
        self.assertEqual(len(self.database.customers), 1)
        saved_customer = next(iter(self.database.customers.values()))
        self.assertEqual(saved_customer, {"customer": "fob customer a", "operator": "KHT"})
        self.assertEqual(next(iter(self.database.sales.values()))["so"], 100)

    def test_update_and_delete_manual_fob_sale(self):
        self.save({
            "date": "2026-05-19",
            "customer": "FOB Customer A",
            "operator": "SETU",
            "so": 15000,
            "actual": 2065,
        })

        updated = self.update(1, {
            "customer": "FOB Customer B",
            "operator": "KHT",
            "so": 12000,
            "actual": 7000,
        })

        self.assertEqual(updated["diff"], -5000)
        self.assertEqual(self.database.sales[1]["so"], 12000)
        self.assertEqual(self.database.sales[1]["actual"], 7000)
        self.assertEqual(self.database.customers[self.database.sales[1]["customer_key"]], {
            "customer": "FOB Customer B",
            "operator": "KHT",
        })
        self.assertEqual(self.delete(1), {"ok": True})
        self.assertEqual(self.database.sales, {})

    def test_rejects_invalid_date_operator_and_negative_amount(self):
        base = {"date": "2026-08-31", "customer": "FOB Customer A", "operator": "KHT", "so": 100, "actual": 90}
        for changes in (
            {"date": "invalid"},
            {"operator": "OFF"},
            {"so": -1},
        ):
            with self.subTest(changes=changes), self.assertRaises(main.HTTPException):
                self.save({**base, **changes})

    def test_requires_login(self):
        with self.assertRaises(main.HTTPException) as error:
            self.save({}, authenticated=False)

        self.assertEqual(error.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
