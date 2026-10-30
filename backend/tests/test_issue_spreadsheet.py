import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class IssueSpreadsheetTests(unittest.TestCase):
    def test_parse_sheet_rows_and_normalize_status(self):
        csv_text = (
            "Timestamp,Customer (PT),Customer PIC,Terjadinya keluhan,"
            "Jenis Keluhan,Root cause,Dampak keluhan,"
            "File Pendukung (Foto/Video/Surat/Screenshoot),Tindakan Segera,"
            "Update terakhir,Tindakan Corrective,Target Date,Status\n"
            "1,PT Contoh,PIC Contoh,16/02/2026,Kualitas Gas,"
            "\"Penyebab pertama\nPenyebab kedua\",Dampak,,Tindakan,"
            "Update,Corrective,30 Apr,closed\n"
        )

        result = main.parse_issue_spreadsheet(csv_text)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["date"], "2026-02-16")
        self.assertEqual(result[0]["status"], "Closed")
        self.assertEqual(result[0]["rootCause"], "Penyebab pertama\nPenyebab kedua")
        self.assertEqual(result[0]["targetDate"], "30 Apr")

    def test_reject_sheet_missing_required_headers(self):
        with self.assertRaisesRegex(ValueError, "Header wajib"):
            main.parse_issue_spreadsheet("Customer,Status\nPT Contoh,Open\n")

    def test_reject_invalid_issue_date(self):
        csv_text = (
            "Customer (PT),Terjadinya keluhan,Jenis Keluhan,Status\n"
            "PT Contoh,tanggal tidak valid,Kualitas Gas,Open\n"
        )
        with self.assertRaisesRegex(ValueError, "Tanggal keluhan tidak valid"):
            main.parse_issue_spreadsheet(csv_text)

    def test_issue_endpoint_requires_login(self):
        request = SimpleNamespace(session={})
        with self.assertRaises(HTTPException) as error:
            main.list_issues(request)
        self.assertEqual(error.exception.status_code, 401)

    def test_issue_endpoint_returns_spreadsheet_data_for_admin(self):
        request = SimpleNamespace(session={"username": main.APP_USERNAME})
        response = {"issues": [], "syncedAt": "2026-10-30T09:00:00+07:00"}
        with patch("main.get_issue_spreadsheet_data", return_value=response):
            self.assertEqual(main.list_issues(request), response)

    def test_fetch_sheet_with_read_only_service_account(self):
        response_queue = [
            SimpleNamespace(
                status_code=200,
                raise_for_status=lambda: None,
                json=lambda: {
                    "sheets": [{
                        "properties": {
                            "sheetId": 418759575,
                            "title": "Monitoring Issue",
                        },
                    }],
                },
            ),
            SimpleNamespace(
                status_code=200,
                raise_for_status=lambda: None,
                json=lambda: {
                    "values": [
                        [
                            "Customer (PT)",
                            "Customer PIC",
                            "Terjadinya keluhan",
                            "Jenis Keluhan",
                            "Status",
                        ],
                        ["PT Contoh", "PIC", "16/02/2026", "Kualitas Gas", "Open"],
                    ],
                },
            ),
        ]
        session = SimpleNamespace(get=lambda *args, **kwargs: response_queue.pop(0))

        with tempfile.TemporaryDirectory() as directory:
            credential_path = Path(directory) / "service-account.json"
            credential_path.write_text(json.dumps({"client_email": "readonly@example.test"}))
            with (
                patch.object(main, "ISSUE_GOOGLE_SERVICE_ACCOUNT_FILE", str(credential_path)),
                patch.object(main.Credentials, "from_service_account_info", return_value=object()) as credentials,
                patch.object(main, "AuthorizedSession", return_value=session),
            ):
                csv_text = main.fetch_issue_sheet_with_service_account()

        self.assertIn("PT Contoh", csv_text)
        self.assertEqual(
            credentials.call_args.kwargs["scopes"],
            ["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )

    def test_missing_service_account_uses_public_csv_fallback(self):
        with patch.object(
            main,
            "ISSUE_GOOGLE_SERVICE_ACCOUNT_FILE",
            "missing-issue-service-account.json",
        ):
            self.assertIsNone(main.fetch_issue_sheet_with_service_account())


if __name__ == "__main__":
    unittest.main()
