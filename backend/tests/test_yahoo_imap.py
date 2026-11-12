import sys
import unittest
from contextlib import nullcontext
from datetime import datetime
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
import yahoo_imap


def build_message(
    *,
    sender="reethauplanner@gmail.com",
    subject="Daily Report Tanggal 09 November 2026",
    filename="11.2026_11_Daily Sales.xlsx",
    message_id="<daily-report-2026-11-09@example.com>",
):
    message = EmailMessage()
    message["From"] = sender
    message["To"] = "dashboard@example.com"
    message["Subject"] = subject
    message["Date"] = "Tue, 10 Nov 2026 09:57:00 +0700"
    message["Message-ID"] = message_id
    message.set_content("Daily sales report")
    if filename:
        message.add_attachment(
            b"workbook-content",
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
        )
    return message.as_bytes()


class FakeMailbox:
    def __init__(self, raw_message):
        self.raw_message = raw_message
        self.header = raw_message.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
        self.full_fetch_count = 0

    def login(self, *_):
        return "OK", []

    def select(self, folder, readonly=False):
        self.selected_folder = folder
        self.readonly = readonly
        return "OK", [b"1"]

    def search(self, charset, *criteria):
        self.search_charset = charset
        self.search_criteria = criteria
        return "OK", [b"1"]

    def fetch(self, message_set, query):
        self.last_message_set = message_set
        if "HEADER" in query:
            response = (
                b"1 (BODY[HEADER] {"
                + str(len(self.header)).encode("ascii")
                + b"} RFC822.SIZE "
                + str(len(self.raw_message)).encode("ascii")
                + b")"
            )
            return "OK", [(response, self.header), b")"]

        self.full_fetch_count += 1
        response = (
            b"1 (BODY[] {"
            + str(len(self.raw_message)).encode("ascii")
            + b"})"
        )
        return "OK", [(response, self.raw_message), b")"]

    def logout(self):
        return "BYE", []


class FakeMailboxWithMessages(FakeMailbox):
    def __init__(self, messages):
        self.messages = messages
        self.full_fetch_count = 0

    def search(self, charset, *criteria):
        self.search_charset = charset
        self.search_criteria = criteria
        return "OK", [" ".join(str(sequence) for sequence in self.messages).encode()]

    def fetch(self, message_set, query):
        if "HEADER" in query:
            response = []
            for sequence in map(int, message_set.split(",")):
                raw_message = self.messages[sequence]
                header = raw_message.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
                item_header = (
                    f"{sequence} (BODY[HEADER] {{{len(header)}}} RFC822.SIZE "
                    f"{len(raw_message)})"
                ).encode()
                response.extend([(item_header, header), b")"])
            return "OK", response

        sequence = int(message_set)
        raw_message = self.messages[sequence]
        self.full_fetch_count += 1
        response = (
            f"{sequence} (BODY[] {{{len(raw_message)}}})".encode()
        )
        return "OK", [(response, raw_message), b")"]


class YahooImapEmailParsingTests(unittest.TestCase):
    def test_uses_the_fixed_planner_sender_address(self):
        with patch.dict("os.environ", {
            "YAHOO_EMAIL": "dashboard@example.com",
            "YAHOO_APP_PASSWORD": "test-app-password",
            "YAHOO_ALLOWED_SENDER": "reethuplanner@gmail.com",
        }):
            settings = yahoo_imap._settings()

        self.assertEqual(settings[4], "reethauplanner@gmail.com")

    def test_extracts_daily_sales_excel_from_planner_email(self):
        parsed = yahoo_imap.parse_daily_sales_email(
            build_message(),
            "reethauplanner@gmail.com",
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(
            parsed["message_id"],
            "<daily-report-2026-11-09@example.com>",
        )
        self.assertEqual(parsed["subject"], "Daily Report Tanggal 09 November 2026")
        self.assertEqual(len(parsed["attachments"]), 1)
        self.assertEqual(
            parsed["attachments"][0]["filename"],
            "11.2026_11_Daily Sales.xlsx",
        )
        self.assertEqual(
            parsed["attachments"][0]["content"],
            b"workbook-content",
        )

    def test_ignores_emails_from_other_senders_or_subjects(self):
        for raw_message in (
            build_message(sender="someone@example.com"),
            build_message(subject="Daily Sales file"),
            build_message(message_id=""),
        ):
            with self.subTest(raw_message=raw_message[:60]):
                self.assertIsNone(
                    yahoo_imap.parse_daily_sales_email(
                        raw_message,
                        "reethauplanner@gmail.com",
                    )
                )

    def test_ignores_non_daily_sales_attachments(self):
        parsed = yahoo_imap.parse_daily_sales_email(
            build_message(filename="Other_Report.xlsx"),
            "reethauplanner@gmail.com",
        )

        self.assertEqual(parsed["attachments"], [])

    def test_subject_match_allows_reply_prefix(self):
        parsed = yahoo_imap.parse_daily_sales_email(
            build_message(subject="Re: Daily Report Tanggal 09 November 2026"),
            "reethauplanner@gmail.com",
        )

        self.assertIsNotNone(parsed)

    def test_reads_imap_size_from_tuple_response(self):
        self.assertEqual(
            yahoo_imap._message_size(
                [(b"1 (BODY[HEADER] {20} RFC822.SIZE 12345)", b"header")]
            ),
            12345,
        )

    def test_fetches_only_new_daily_sales_messages(self):
        mailbox = FakeMailbox(build_message())
        with (
            patch.dict("os.environ", {
                "YAHOO_EMAIL": "dashboard@example.com",
                "YAHOO_APP_PASSWORD": "test-app-password",
                "YAHOO_ALLOWED_SENDER": "reethauplanner@gmail.com",
            }),
            patch.object(yahoo_imap.imaplib, "IMAP4_SSL", return_value=mailbox),
        ):
            emails = yahoo_imap.fetch_daily_sales_emails()

        self.assertEqual(len(emails), 1)
        self.assertEqual(len(emails[0]["attachments"]), 1)
        self.assertEqual(mailbox.full_fetch_count, 1)
        self.assertEqual(
            mailbox.search_criteria,
            ("FROM", '"reethauplanner@gmail.com"'),
        )

        with (
            patch.dict("os.environ", {
                "YAHOO_EMAIL": "dashboard@example.com",
                "YAHOO_APP_PASSWORD": "test-app-password",
                "YAHOO_ALLOWED_SENDER": "reethauplanner@gmail.com",
            }),
            patch.object(yahoo_imap.imaplib, "IMAP4_SSL", return_value=mailbox),
        ):
            emails = yahoo_imap.fetch_daily_sales_emails({
                "<daily-report-2026-11-09@example.com>"
            })

        self.assertEqual(emails, [])
        self.assertEqual(mailbox.full_fetch_count, 1)

    def test_scans_past_latest_processed_email_for_unprocessed_message(self):
        older_message = build_message(
            message_id="<older-daily-report@example.com>",
        )
        latest_message = build_message(
            message_id="<latest-daily-report@example.com>",
            subject="Daily Report Tanggal 10 November 2026",
        )
        mailbox = FakeMailboxWithMessages({
            1: older_message,
            2: latest_message,
        })
        with (
            patch.dict("os.environ", {
                "YAHOO_EMAIL": "dashboard@example.com",
                "YAHOO_APP_PASSWORD": "test-app-password",
                "YAHOO_ALLOWED_SENDER": "reethauplanner@gmail.com",
            }),
            patch.object(yahoo_imap.imaplib, "IMAP4_SSL", return_value=mailbox),
        ):
            emails = yahoo_imap.fetch_daily_sales_emails({
                "<latest-daily-report@example.com>"
            })

        self.assertEqual(
            [email["message_id"] for email in emails],
            ["<older-daily-report@example.com>"],
        )
        self.assertEqual(mailbox.full_fetch_count, 1)

    def test_fetches_all_unprocessed_daily_report_messages_in_scan_window(self):
        mailbox = FakeMailboxWithMessages({
            1: build_message(message_id="<report-one@example.com>"),
            2: build_message(
                subject="Daily Report Tanggal 10 November 2026",
                message_id="<report-two@example.com>",
            ),
        })
        with (
            patch.dict("os.environ", {
                "YAHOO_EMAIL": "dashboard@example.com",
                "YAHOO_APP_PASSWORD": "test-app-password",
                "YAHOO_ALLOWED_SENDER": "reethauplanner@gmail.com",
            }),
            patch.object(yahoo_imap.imaplib, "IMAP4_SSL", return_value=mailbox),
        ):
            emails = yahoo_imap.fetch_daily_sales_emails()

        self.assertEqual(
            [email["message_id"] for email in emails],
            ["<report-one@example.com>", "<report-two@example.com>"],
        )
        self.assertEqual(mailbox.full_fetch_count, 2)


class YahooDailySalesSyncTests(unittest.TestCase):
    def test_extracts_report_date_from_daily_report_subject(self):
        report_date = main.daily_report_date_from_subject(
            "Daily Report Tanggal 11 November 2026"
        )
        self.assertEqual(report_date, main.date(2026, 11, 11))
        self.assertEqual(
            main.daily_report_import_dates(
                report_date,
                "2026-11-01",
                "2026-11-30",
            ),
            {main.date(2026, 11, 10), main.date(2026, 11, 11)},
        )
        self.assertEqual(
            main.daily_report_import_dates(
                main.date(2026, 11, 1),
                "2026-11-01",
                "2026-11-30",
            ),
            {main.date(2026, 11, 1)},
        )

        with self.assertRaisesRegex(ValueError, "tidak dapat dibaca"):
            main.daily_report_date_from_subject("Daily Report November 2026")

    def test_email_message_is_claimed_only_once(self):
        stored_hashes = set()

        class FakeCursor:
            def __init__(self, rowcount):
                self.rowcount = rowcount

        class FakeConnection:
            def execute(self, statement, parameters):
                if statement.startswith("INSERT IGNORE"):
                    message_hash = parameters[0]
                    if message_hash in stored_hashes:
                        return FakeCursor(0)
                    stored_hashes.add(message_hash)
                    return FakeCursor(1)
                return FakeCursor(0)

        connection = FakeConnection()
        with patch.object(main, "db", side_effect=lambda: nullcontext(connection)):
            first = main._claim_email_import(
                "<unique-daily-report@example.com>",
                "Daily Report Tanggal 09 November 2026",
            )
            second = main._claim_email_import(
                "<unique-daily-report@example.com>",
                "Daily Report Tanggal 09 November 2026",
            )

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(stored_hashes), 1)

    def test_legacy_imported_email_is_reclaimed_for_date_filtered_backfill(self):
        class FakeCursor:
            rowcount = 1

        class FakeConnection:
            def __init__(self):
                self.update = None

            def execute(self, statement, parameters):
                if statement.startswith("INSERT IGNORE"):
                    return type("InsertResult", (), {"rowcount": 0})()
                self.update = (statement, parameters)
                return FakeCursor()

        connection = FakeConnection()
        with patch.object(main, "db", side_effect=lambda: nullcontext(connection)):
            claimed = main._claim_email_import(
                "<legacy-daily-report@example.com>",
                "Daily Report Tanggal 10 November 2026",
            )

        self.assertIsNotNone(claimed)
        statement, parameters = connection.update
        self.assertIn("status='IMPORTED'", statement)
        self.assertIn("NOT LIKE %s", statement)
        self.assertEqual(
            parameters[1],
            f"{main.EMAIL_IMPORT_DATE_FILTER_MARKER}%",
        )

    def test_disabled_sync_does_not_connect_to_mailbox(self):
        request = SimpleNamespace()
        with (
            patch.object(main, "require_admin"),
            patch.object(main, "YAHOO_SYNC_ENABLED", False),
            patch.object(main, "fetch_daily_sales_emails") as fetch,
        ):
            result = main.sync_daily_sales_email(request)

        self.assertFalse(result["enabled"])
        self.assertEqual(result["imported"], [])
        fetch.assert_not_called()

    def test_validates_daily_sales_workbook_and_date_range(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Daily Sales"
        sheet.cell(3, 2, "CUSTOMER A")
        sheet.cell(4, 3, "ACTUAL")
        sheet.cell(5, 2, datetime(2026, 11, 9))
        sheet.cell(5, 3, 123.45)
        content = BytesIO()
        workbook.save(content)
        workbook.close()

        result = main.validate_email_daily_sales_workbook(content.getvalue())

        self.assertEqual(result, {
            "rows_read": 1,
            "start_date": "2026-11-09",
            "end_date": "2026-11-09",
        })

    def test_rejects_workbooks_without_supported_daily_sales_sheets(self):
        workbook = Workbook()
        workbook.active.title = "Summary"
        content = BytesIO()
        workbook.save(content)
        workbook.close()

        with self.assertRaisesRegex(ValueError, "tidak berisi sheet Daily Sales"):
            main.validate_email_daily_sales_workbook(content.getvalue())
