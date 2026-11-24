import asyncio
from datetime import date, datetime
from io import BytesIO
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cooperation
import main


def build_workbook(include_expired_summary=False, include_summary_title=True):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "kontrak"
    worksheet.cell(6, 2, "Code")
    worksheet.cell(6, 3, "Customer")
    worksheet.cell(8, 2, "duplicate-code")
    worksheet.cell(8, 3, "Customer A")
    worksheet.cell(8, 8, 120)
    worksheet.cell(8, 20, datetime(2024, 1, 2))
    worksheet.cell(8, 22, datetime(2026, 12, 31))
    worksheet.cell(9, 2, "duplicate-code")
    worksheet.cell(9, 3, "Customer B")
    worksheet.cell(9, 22, None)
    worksheet.cell(10, 2, "code-only-row")
    worksheet.cell(11, 9, 250)
    if include_expired_summary:
        if include_summary_title:
            worksheet.cell(12, 1, "Customer yang habis kontrak di tahun 2023")
        worksheet.cell(13, 2, "No")
        worksheet.cell(13, 3, "Nama Customer")
        worksheet.cell(14, 2, 1)
        worksheet.cell(14, 3, "Expired Customer")
        worksheet.cell(14, 4, datetime(2023, 1, 1))
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


class FakeRequest:
    def __init__(self, role="admin"):
        self.session = {
            "username": "test-admin" if role == "admin" else "test-user",
            "role": role,
        }


class FakeUpload:
    filename = "contracts.xlsx"

    def __init__(self, content):
        self.content = content

    async def read(self):
        return self.content


class MemoryDatabase:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, parameters=None):
        self.statements.append((statement, parameters))
        return SimpleNamespace(rowcount=1)


class MemoryContractsDatabase:
    def __init__(self, contracts):
        self.contracts = contracts
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, statement, *_):
        self.statements.append(statement)
        return SimpleNamespace(fetchall=lambda: self.contracts)


class CooperationWorkbookTests(unittest.TestCase):
    def test_parser_keeps_duplicate_codes_and_empty_end_dates(self):
        records = cooperation.parse_cooperation_workbook(build_workbook())

        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["code"], "duplicate-code")
        self.assertEqual(records[1]["code"], "duplicate-code")
        self.assertEqual(records[2]["code"], "code-only-row")
        self.assertEqual(records[2]["customer"], "")
        self.assertEqual(records[0]["volume_min_mmbtu"], "120")
        self.assertEqual(records[0]["end_contract_date"].isoformat(), "2026-12-31")
        self.assertEqual(records[1]["end_of_contract"], "")
        self.assertIsNone(records[1]["end_contract_date"])

    def test_parser_stops_before_expired_customer_appendix(self):
        records = cooperation.parse_cooperation_workbook(
            build_workbook(include_expired_summary=True)
        )

        self.assertEqual(len(records), 3)
        self.assertNotIn("Nama Customer", [record["customer"] for record in records])
        self.assertNotIn("Expired Customer", [record["customer"] for record in records])

    def test_parser_stops_at_appendix_header_without_title(self):
        records = cooperation.parse_cooperation_workbook(
            build_workbook(
                include_expired_summary=True,
                include_summary_title=False,
            )
        )

        self.assertEqual(len(records), 3)
        self.assertNotIn("Nama Customer", [record["customer"] for record in records])

    def test_parser_handles_indonesian_text_dates(self):
        self.assertEqual(
            cooperation.parse_contract_date("31-Maret-2025").isoformat(),
            "2025-03-31",
        )
        self.assertEqual(
            cooperation.parse_contract_date("2 okt 2019").isoformat(),
            "2019-10-02",
        )
        self.assertEqual(
            cooperation.parse_contract_date("Desember 2027").isoformat(),
            "2027-12-31",
        )

    def test_parser_rejects_invalid_workbooks_and_missing_contract_sheet(self):
        with self.assertRaisesRegex(ValueError, "tidak dapat dibaca"):
            cooperation.parse_cooperation_workbook(b"not an Excel file")

        workbook = Workbook()
        workbook.active.title = "Sheet1"
        output = BytesIO()
        workbook.save(output)
        workbook.close()
        with self.assertRaisesRegex(ValueError, "Sheet bernama"):
            cooperation.parse_cooperation_workbook(output.getvalue())

    def test_admin_import_replaces_rows_without_using_code_as_a_unique_key(self):
        database = MemoryDatabase()
        with patch.object(main, "db", return_value=database):
            result = asyncio.run(
                main.import_cooperation_workbook(
                    FakeRequest(),
                    FakeUpload(build_workbook()),
                )
            )

        self.assertEqual(result["imported"], 3)
        self.assertEqual(database.statements[0][0], "DELETE FROM cooperation_contracts")
        inserts = [
            (statement, parameters)
            for statement, parameters in database.statements
            if statement.startswith("INSERT INTO cooperation_contracts")
        ]
        self.assertEqual(len(inserts), 3)
        self.assertEqual(inserts[0][1][1], "duplicate-code")
        self.assertEqual(inserts[1][1][1], "duplicate-code")
        self.assertEqual(len(inserts[0][1]), 26)
        self.assertIsNone(inserts[1][1][-1])

    def test_regular_user_cannot_import_workbooks(self):
        with self.assertRaises(main.HTTPException) as error:
            asyncio.run(
                main.import_cooperation_workbook(
                    FakeRequest(role="user"),
                    FakeUpload(build_workbook()),
                )
            )

        self.assertEqual(error.exception.status_code, 403)

    def test_list_derives_status_without_assigning_one_to_blank_end_dates(self):
        database = MemoryContractsDatabase([
            {"id": 1, "end_contract_date": date(2026, 1, 10)},
            {"id": 2, "end_contract_date": date(2025, 12, 31)},
            {"id": 3, "end_contract_date": None},
        ])
        with (
            patch.object(main, "db", return_value=database),
            patch.object(main, "_business_today", return_value=date(2026, 1, 1)),
        ):
            contracts = main.list_cooperation_contracts(FakeRequest())

        self.assertIn(
            "SELECT id,sort_order,code,customer,address,mother_station,",
            database.statements[0],
        )
        self.assertEqual(
            [(row["status"], row["days_remaining"]) for row in contracts],
            [("active", 9), ("ended", -1), ("undated", None)],
        )

    def test_list_omits_legacy_expired_customer_appendix(self):
        database = MemoryContractsDatabase([
            {
                "id": 1,
                "code": "C-1",
                "customer": "Customer A",
                "end_contract_date": date(2026, 1, 10),
            },
            {
                "id": 2,
                "code": "Customer yang habis kontrak di 2023",
                "customer": "",
                "end_contract_date": None,
            },
            {
                "id": 3,
                "code": "No",
                "customer": "Nama Customer",
                "end_contract_date": None,
            },
            {
                "id": 4,
                "code": "1",
                "customer": "Expired Customer",
                "end_contract_date": date(2023, 1, 1),
            },
        ])
        with (
            patch.object(main, "db", return_value=database),
            patch.object(main, "_business_today", return_value=date(2026, 1, 1)),
        ):
            contracts = main.list_cooperation_contracts(FakeRequest())

        self.assertEqual([contract["customer"] for contract in contracts], ["Customer A"])

    def test_regular_user_receives_only_contract_validity_fields(self):
        database = MemoryContractsDatabase([
            {
                "id": 1,
                "code": "C-1",
                "customer": "Customer A",
                "agreement_number": "AGR-1",
                "end_of_contract": "31-Dec-2026",
                "end_contract_date": date(2026, 12, 31),
            },
        ])
        with (
            patch.object(main, "require_login"),
            patch.object(main, "db", return_value=database),
            patch.object(main, "_business_today", return_value=date(2026, 1, 1)),
        ):
            contracts = main.list_cooperation_contracts(FakeRequest(role="user"))

        self.assertIn("SELECT id,code,customer,agreement_number,end_of_contract,end_contract_date", database.statements[0])
        self.assertEqual(
            set(contracts[0]),
            {
                "id",
                "code",
                "customer",
                "agreement_number",
                "end_of_contract",
                "end_contract_date",
                "days_remaining",
                "status",
            },
        )
        self.assertEqual(contracts[0]["days_remaining"], 364)


if __name__ == "__main__":
    unittest.main()
