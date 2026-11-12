import imaplib
import os
import re
import ssl
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parseaddr

MAX_ATTACHMENT_BYTES = 30 * 1024 * 1024
MAX_EMAIL_BYTES = 35 * 1024 * 1024
MAX_MESSAGES_TO_SCAN = 20


def decode_value(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _settings():
    host = os.getenv("YAHOO_IMAP_HOST", "imap.mail.yahoo.com").strip()
    try:
        port = int(os.getenv("YAHOO_IMAP_PORT", "993"))
    except ValueError as exc:
        raise RuntimeError("YAHOO_IMAP_PORT harus berupa angka.") from exc
    email_address = os.getenv("YAHOO_EMAIL", "").strip()
    password = os.getenv("YAHOO_APP_PASSWORD", "").strip()
    allowed_sender = os.getenv(
        "YAHOO_ALLOWED_SENDER",
        "reethauplanner@gmail.com",
    ).strip().lower()
    folder = os.getenv("YAHOO_IMAP_FOLDER", "INBOX").strip()

    if not email_address or not password:
        raise RuntimeError(
            "YAHOO_EMAIL atau YAHOO_APP_PASSWORD belum dikonfigurasi."
        )
    if not host or not 1 <= port <= 65535:
        raise RuntimeError("Konfigurasi server IMAP tidak valid.")
    if not allowed_sender or not folder:
        raise RuntimeError("Pengirim Planner dan folder IMAP harus dikonfigurasi.")
    return host, port, email_address, password, allowed_sender, folder


def _connect_mailbox(settings):
    host, port, email_address, password, _, _ = settings
    mailbox = None
    try:
        mailbox = imaplib.IMAP4_SSL(
            host,
            port,
            ssl_context=ssl.create_default_context(),
            timeout=20,
        )
        mailbox.login(email_address, password)
        return mailbox
    except imaplib.IMAP4.error as exc:
        if mailbox is not None:
            try:
                mailbox.logout()
            except (imaplib.IMAP4.error, OSError):
                pass
        raise RuntimeError(
            "Login IMAP gagal. Periksa username dan App Password."
        ) from exc
    except OSError as exc:
        if mailbox is not None:
            try:
                mailbox.logout()
            except (imaplib.IMAP4.error, OSError):
                pass
        raise RuntimeError("Tidak dapat terhubung ke server IMAP.") from exc


def _header_bytes(response):
    return next(
        (
            item[1]
            for item in response or ()
            if isinstance(item, tuple) and isinstance(item[1], bytes)
        ),
        None,
    )


def _is_daily_report(subject):
    return bool(re.match(r"^\s*(?:re:\s*)*daily report tanggal\b", subject, re.I))


def parse_daily_sales_email(raw_message, allowed_sender):
    message = message_from_bytes(raw_message)
    sender = parseaddr(message.get("From", ""))[1].strip().lower()
    subject = decode_value(message.get("Subject"))
    message_id = message.get("Message-ID", "").strip()
    if sender != allowed_sender or not _is_daily_report(subject) or not message_id:
        return None

    attachments = []
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = decode_value(part.get_filename()).strip()
        normalized_filename = re.sub(r"[_-]+", " ", filename).lower()
        if (
            not filename.lower().endswith((".xlsx", ".xlsm"))
            or "daily sales" not in normalized_filename
        ):
            continue
        content = part.get_payload(decode=True)
        if not content:
            continue
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise ValueError(
                f"Lampiran {filename} melebihi batas ukuran 30 MB."
            )
        attachments.append({"filename": filename, "content": content})

    return {
        "message_id": message_id,
        "subject": subject,
        "date": message.get("Date", ""),
        "sender": sender,
        "attachments": attachments,
    }


def _message_size(response):
    raw = b" ".join(
        item[0] if isinstance(item, tuple) and isinstance(item[0], bytes)
        else item if isinstance(item, bytes)
        else b""
        for item in response or ()
    )
    match = re.search(rb"RFC822\.SIZE\s+(\d+)", raw, re.I)
    return int(match.group(1)) if match else None


def fetch_daily_sales_emails(processed_message_ids=None):
    settings = _settings()
    _, _, _, _, allowed_sender, folder = settings
    mailbox = _connect_mailbox(settings)
    emails = []
    processed_message_ids = set(processed_message_ids or ())
    try:
        status, _ = mailbox.select(folder, readonly=True)
        if status != "OK":
            raise RuntimeError("Folder email yang dikonfigurasi tidak dapat dibuka.")

        status, data = mailbox.search(
            None,
            "FROM",
            f'"{allowed_sender}"',
            "SUBJECT",
            '"Daily Report Tanggal"',
        )
        if status != "OK":
            raise RuntimeError("Pencarian email Planner gagal.")

        message_ids = data[0].split() if data and data[0] else []
        recent_ids = message_ids[-MAX_MESSAGES_TO_SCAN:]
        if not recent_ids:
            return []
        sequence_set = ",".join(message_id.decode("ascii") for message_id in recent_ids)
        status, response = mailbox.fetch(
            sequence_set,
            "(BODY.PEEK[HEADER] RFC822.SIZE)",
        )
        if status != "OK":
            raise RuntimeError("Header email Planner gagal dibaca.")

        candidates = []
        for item in response or ():
            if not isinstance(item, tuple) or not item or not item[0]:
                continue
            message_id = re.match(rb"^(\d+)", item[0])
            if not message_id:
                continue
            raw_header = item[1] if isinstance(item[1], bytes) else None
            if not raw_header:
                continue
            header = message_from_bytes(raw_header)
            sender = parseaddr(header.get("From", ""))[1].strip().lower()
            subject = decode_value(header.get("Subject"))
            if sender != allowed_sender or not _is_daily_report(subject):
                continue
            header_message_id = header.get("Message-ID", "").strip()
            if not header_message_id or header_message_id in processed_message_ids:
                continue

            size = _message_size([item])
            if size is not None and size > MAX_EMAIL_BYTES:
                emails.append({
                    "message_id": header_message_id,
                    "subject": subject,
                    "date": header.get("Date", ""),
                    "sender": sender,
                    "attachments": [],
                    "error": "Ukuran email melebihi batas pemrosesan.",
                })
                continue
            candidates.append((int(message_id.group(1)), header_message_id))

        for sequence_number, _ in sorted(candidates, reverse=True):
            status, full_response = mailbox.fetch(
                str(sequence_number),
                "(BODY.PEEK[])",
            )
            if status != "OK":
                continue
            raw_message = _header_bytes(full_response)
            if not raw_message:
                continue
            parsed = parse_daily_sales_email(raw_message, allowed_sender)
            if parsed:
                emails.append(parsed)
                break
    except imaplib.IMAP4.error as exc:
        raise RuntimeError("Operasi pencarian email IMAP gagal.") from exc
    except OSError as exc:
        raise RuntimeError("Koneksi ke server IMAP terputus.") from exc
    finally:
        try:
            mailbox.logout()
        except (imaplib.IMAP4.error, OSError):
            pass

    return emails


def test_connection():
    settings = _settings()
    _, _, email_address, _, allowed_sender, folder = settings
    mailbox = _connect_mailbox(settings)
    try:
        status, _ = mailbox.select(folder, readonly=True)
        if status != "OK":
            raise RuntimeError("Folder email yang dikonfigurasi tidak dapat dibuka.")
        status, data = mailbox.search(None, "FROM", f'"{allowed_sender}"')
        if status != "OK":
            raise RuntimeError("Pencarian email gagal.")

        messages = []
        message_ids = data[0].split() if data and data[0] else []
        for message_id in reversed(message_ids[-10:]):
            status, response = mailbox.fetch(
                message_id,
                "(BODY.PEEK[HEADER])",
            )
            if status != "OK":
                continue
            raw_header = _header_bytes(response)
            if not raw_header:
                continue
            message = message_from_bytes(raw_header)
            sender = parseaddr(message.get("From", ""))[1].strip().lower()
            if sender != allowed_sender:
                continue
            messages.append({
                "sender": sender,
                "subject": decode_value(message.get("Subject")),
                "date": message.get("Date", ""),
                "message_id": message.get("Message-ID", ""),
            })

        return {
            "ok": True,
            "mailbox": email_address,
            "folder": folder,
            "allowed_sender": allowed_sender,
            "matching_emails": len(messages),
            "messages": messages,
            "message": "Koneksi IMAP berhasil.",
        }
    except imaplib.IMAP4.error as exc:
        raise RuntimeError("Operasi IMAP gagal.") from exc
    finally:
        try:
            mailbox.logout()
        except (imaplib.IMAP4.error, OSError):
            pass
