import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import db


class MigrationConnection:
    def __init__(self, columns):
        self.columns = set(columns)
        self.statements = []

    def execute(self, statement, parameters=None):
        self.statements.append(statement)
        if "information_schema.COLUMNS" in statement:
            return SimpleNamespace(
                fetchall=lambda: [{"COLUMN_NAME": column} for column in self.columns]
            )
        column_name = statement.split("ADD COLUMN ", 1)[1].split()[0]
        self.columns.add(column_name)
        return SimpleNamespace()


class DatabaseMigrationTests(unittest.TestCase):
    def test_customer_off_date_migration_adds_missing_column(self):
        connection = MigrationConnection({"customer_key", "operator"})

        db._ensure_customer_off_date_column(connection)

        self.assertIn("off_from_date", connection.columns)
        self.assertEqual(
            sum("ALTER TABLE customers" in statement for statement in connection.statements),
            1,
        )

    def test_customer_off_date_migration_preserves_existing_column(self):
        connection = MigrationConnection(
            {"customer_key", "operator", "off_from_date"}
        )

        db._ensure_customer_off_date_column(connection)

        self.assertEqual(
            sum("ALTER TABLE customers" in statement for statement in connection.statements),
            0,
        )

    def test_contract_date_migration_adds_missing_columns_only(self):
        connection = MigrationConnection({"proposal_number"})

        db._ensure_sph_contract_date_columns(connection)

        self.assertIn("start_date", connection.columns)
        self.assertIn("end_date", connection.columns)
        self.assertEqual(
            sum("ALTER TABLE sph_proposals" in statement for statement in connection.statements),
            2,
        )

    def test_contract_date_migration_preserves_existing_columns(self):
        connection = MigrationConnection({"start_date", "end_date"})

        db._ensure_sph_contract_date_columns(connection)

        self.assertEqual(
            sum("ALTER TABLE sph_proposals" in statement for statement in connection.statements),
            0,
        )

    def test_sph_offer_details_migration_adds_missing_column(self):
        connection = MigrationConnection({"proposal_number"})

        db._ensure_sph_offer_details_column(connection)

        self.assertIn("offer_details", connection.columns)
        self.assertEqual(
            sum("ALTER TABLE sph_proposals" in statement for statement in connection.statements),
            1,
        )

    def test_sph_offer_details_migration_preserves_existing_column(self):
        connection = MigrationConnection({"proposal_number", "offer_details"})

        db._ensure_sph_offer_details_column(connection)

        self.assertEqual(
            sum("ALTER TABLE sph_proposals" in statement for statement in connection.statements),
            0,
        )


if __name__ == "__main__":
    unittest.main()
