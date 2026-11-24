import calendar
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import re
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException


COOPERATION_FIELDS = (
    "code",
    "customer",
    "address",
    "mother_station",
    "forms_of_cooperation",
    "agreement_number",
    "volume_min_mmbtu",
    "volume_max_mmbtu",
    "volume_min_sm3",
    "volume_max_sm3",
    "volume_min_nm3",
    "volume_max_nm3",
    "price_usd_mmbtu",
    "price_usd_m3",
    "price_idr_m3",
    "kurs",
    "invoicing",
    "terms_of_payment",
    "contract_signed",
    "gas_in",
    "end_of_contract",
    "remarks",
    "pic_customer",
    "telephone",
)

INDONESIAN_MONTHS = {
    "januari": "January",
    "jan": "January",
    "februari": "February",
    "feb": "February",
    "maret": "March",
    "mar": "March",
    "mei": "May",
    "juni": "June",
    "jun": "June",
    "juli": "July",
    "jul": "July",
    "agustus": "August",
    "agu": "August",
    "ags": "August",
    "okt": "October",
    "oktober": "October",
    "nov": "November",
    "desember": "December",
    "des": "December",
}


def _cell_text(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d-%b-%Y")
    if isinstance(value, date):
        return value.strftime("%d-%b-%Y")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, float):
        return format(value, ".15g")
    return str(value).strip()


def parse_contract_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None

    text = value.strip()
    for indonesian, english in sorted(
        INDONESIAN_MONTHS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        text = re.sub(
            rf"\b{indonesian}\b",
            english,
            text,
            flags=re.IGNORECASE,
        )

    for date_format in (
        "%Y-%m-%d",
        "%d-%b-%Y",
        "%d-%b-%y",
        "%d-%B-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%d/%m/%Y",
        "%d/%m/%y",
    ):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    for date_format in ("%B %Y", "%b %Y"):
        try:
            month = datetime.strptime(text, date_format)
            last_day = calendar.monthrange(month.year, month.month)[1]
            return date(month.year, month.month, last_day)
        except ValueError:
            continue
    return None


def _normalized_label(value):
    return " ".join(_cell_text(value).split()).casefold()


def is_expired_customer_summary_header(code, customer):
    return (
        _normalized_label(code) == "no"
        and _normalized_label(customer) == "nama customer"
    )


def _is_expired_customer_summary_title(row):
    return any(
        "customer yang habis kontrak di" in _normalized_label(value)
        for value in row[:5]
    )


def parse_cooperation_workbook(content):
    try:
        workbook = load_workbook(
            BytesIO(content),
            data_only=True,
            read_only=True,
        )
    except (BadZipFile, InvalidFileException, OSError, ValueError) as exc:
        raise ValueError("File Excel kerja sama tidak dapat dibaca.") from exc

    try:
        worksheet = next(
            (sheet for sheet in workbook.worksheets if sheet.title.strip().casefold() == "kontrak"),
            None,
        )
        if worksheet is None:
            raise ValueError("Sheet bernama 'kontrak' tidak ditemukan.")
        if worksheet.max_row > 5000 or worksheet.max_column > 30:
            raise ValueError("Ukuran sheet kontrak melebihi batas yang didukung.")

        records = []
        for row_number, row in enumerate(
            worksheet.iter_rows(min_row=8, max_col=25, values_only=True),
            start=8,
        ):
            if (
                _is_expired_customer_summary_title(row)
                or is_expired_customer_summary_header(row[1], row[2])
            ):
                break
            if row[1] in (None, "") and row[2] in (None, ""):
                continue
            values = {
                field: _cell_text(row[column])
                for field, column in zip(COOPERATION_FIELDS, range(1, 25))
            }
            values["sort_order"] = row_number
            values["end_contract_date"] = parse_contract_date(row[21])
            records.append(values)
        if not records:
            raise ValueError("Tidak ada data customer pada sheet 'kontrak'.")
        return records
    finally:
        workbook.close()
