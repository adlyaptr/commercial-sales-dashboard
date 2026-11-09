import csv
import calendar
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.parse import parse_qs, quote, unquote, urlsplit
from urllib.request import Request as URLRequest, urlopen
from zoneinfo import ZoneInfo
from zipfile import BadZipFile

import pymysql
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pymysql.cursors import DictCursor
from requests.exceptions import RequestException
from starlette.middleware.sessions import SessionMiddleware
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    from .db import initialize_database
    from .monthly_template_export import build_monthly_template_export
except ImportError:
    from db import initialize_database
    from monthly_template_export import build_monthly_template_export
    
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR / "static" / "react"
SPH_PDF_FONT_DIR = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("SphSans", str(SPH_PDF_FONT_DIR / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("SphSans-Bold", str(SPH_PDF_FONT_DIR / "VeraBd.ttf")))
pdfmetrics.registerFont(TTFont("SphSans-Italic", str(SPH_PDF_FONT_DIR / "VeraIt.ttf")))
pdfmetrics.registerFont(TTFont("SphSans-BoldItalic", str(SPH_PDF_FONT_DIR / "VeraBI.ttf")))
pdfmetrics.registerFontFamily(
    "SphSans",
    normal="SphSans",
    bold="SphSans-Bold",
    italic="SphSans-Italic",
    boldItalic="SphSans-BoldItalic",
)
load_dotenv(BASE_DIR / ".env")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql://root:@127.0.0.1:3306/commercial_sales_dashboard?charset=utf8mb4",
)
INPUT_DIR = BASE_DIR.parent / "database" / "imports"
INPUT_DIR.mkdir(parents=True, exist_ok=True)

APP_USERNAME = os.getenv("APP_USERNAME", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "12345678")
SESSION_SECRET = os.getenv("SESSION_SECRET", "CHANGE-ME-use-a-long-random-secret-before-deployment")
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
SESSION_COOKIE_SECURE = os.getenv(
    "SESSION_COOKIE_SECURE",
    "true" if APP_ENV == "production" else "false",
).strip().lower() == "true"
PASSWORD_HASH_ITERATIONS = 310_000
ISSUE_SHEET_ID = os.getenv(
    "ISSUE_SHEET_ID",
    "19vQxh81PDViOVTKMcIdd8qmG3gHrk374PV_ofVe6kdQ",
).strip()
ISSUE_SHEET_GID = os.getenv("ISSUE_SHEET_GID", "418759575").strip()
ISSUE_GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
    "ISSUE_GOOGLE_SERVICE_ACCOUNT_FILE",
    (
        "/run/secrets/issue-google-service-account.json"
        if APP_ENV == "production"
        else str(BASE_DIR.parent / "secrets" / "issue-google-service-account.json")
    ),
).strip()
AVERAGE_PRICE_SHEET_ID = os.getenv(
    "AVERAGE_PRICE_SHEET_ID",
    "1IoDGktFicMKKzu6m015onxv7WBhreqqwz0j7A_k6T1o",
).strip()
AVERAGE_PRICE_SHEET_GID = os.getenv("AVERAGE_PRICE_SHEET_GID", "421480429").strip()
AVERAGE_PRICE_SHEET_TITLE = os.getenv(
    "AVERAGE_PRICE_SHEET_TITLE",
    "Harga Customer 2026",
).strip()
ISSUE_SHEET_CACHE_SECONDS = 300
_issue_sheet_cache = {"expires_at": 0.0, "data": None}
_issue_sheet_lock = threading.Lock()
SALES_ORDER_SHEET_ID = os.getenv(
    "SALES_ORDER_SHEET_ID",
    "1_xx5K5PFaUF9A6VQgmagQ1QiOEh98YmsQcZtswu1CNI",
).strip()
SALES_ORDER_SHEET_GID = os.getenv("SALES_ORDER_SHEET_GID", "694583576").strip()
SALES_ORDER_CACHE_SECONDS = 300
_sales_order_cache = {"expires_at": 0.0, "data": None}
_sales_order_lock = threading.Lock()
BUDGET_TARGET_SHEET_GID = os.getenv("BUDGET_TARGET_SHEET_GID", "737662524").strip()
BUDGET_FINANCE_SHEET_TITLE = os.getenv("BUDGET_FINANCE_SHEET_TITLE", "Summary Finance").strip()
BUDGET_CACHE_SECONDS = 300
_budget_cache = {"expires_at": 0.0, "data": None}
_budget_lock = threading.Lock()


def validate_runtime_config():
    if APP_ENV != "production":
        return

    required = ("DATABASE_URL", "APP_USERNAME", "APP_PASSWORD", "SESSION_SECRET")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(
            "Konfigurasi production belum lengkap: " + ", ".join(missing)
        )
    if APP_PASSWORD == "12345678" or len(APP_PASSWORD) < 12:
        raise RuntimeError("APP_PASSWORD production harus diganti dan minimal 12 karakter.")
    if SESSION_SECRET.startswith("CHANGE-ME") or len(SESSION_SECRET) < 32:
        raise RuntimeError("SESSION_SECRET production harus berupa secret acak minimal 32 karakter.")
    if not SESSION_COOKIE_SECURE:
        raise RuntimeError("SESSION_COOKIE_SECURE harus true di lingkungan production.")

@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_runtime_config()
    init_db()
    yield


app = FastAPI(title="Commercial Sales Dashboard", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=SESSION_COOKIE_SECURE,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

OPERATORS = ["SETU", "KHT", "BLORA", "WUNUT"]
AVERAGE_PRICE_EXCLUDED_CUSTOMER_KEYS = {"pentawira", "pentawiraren"}
CUSTOMER_ASSIGNMENTS = {*OPERATORS, "OFF"}
REGION_BY_OPERATOR = {
    "SETU": "JAWA BARAT",
    "KHT": "JAWA BARAT",
    "BLORA": "JAWA TENGAH",
    "WUNUT": "JAWA TIMUR",
    "OFF": "JAWA BARAT",
}
REGION_BY_CUSTOMER = {
    "ktn": "JAWA TENGAH",
}
COMPLAINT_TYPES = {
    "Keterlambatan Pekerjaan",
    "Keterlambatan Pengiriman",
    "Perilaku Pekerja",
    "Keselamatan Kerja",
    "Kualitas Suplai Gas CNG",
    "Lainnya",
}
LEGACY_COMPLAINT_TYPES = {"Pasokan Gas", "Operasional", "Administrasi"}


def db():
    parsed_url = urlsplit(DATABASE_URL)
    if parsed_url.scheme not in {"mysql", "mariadb"}:
        raise RuntimeError("DATABASE_URL harus menggunakan skema mysql:// atau mariadb://.")
    query = parse_qs(parsed_url.query)
    connection = pymysql.connect(
        host=parsed_url.hostname or "127.0.0.1",
        port=parsed_url.port or 3306,
        user=unquote(parsed_url.username or "root"),
        password=unquote(parsed_url.password or ""),
        database=unquote(parsed_url.path.lstrip("/")),
        charset=query.get("charset", ["utf8mb4"])[0],
        cursorclass=DictCursor,
        connect_timeout=5,
        autocommit=False,
    )
    return DatabaseConnection(connection)


class DatabaseConnection:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, error_type, *_):
        try:
            if error_type:
                self.connection.rollback()
            else:
                self.connection.commit()
        finally:
            self.connection.close()

    def execute(self, statement, parameters=None):
        cursor = self.connection.cursor()
        cursor.execute(statement, parameters)
        return cursor


def init_db():
    initialize_database(db, APP_USERNAME, APP_PASSWORD)


def logged_in(request: Request) -> bool:
    username = request.session.get("username")
    role = request.session.get("role")
    return bool(username) and (
        role in {"admin", "user"}
        or (username == APP_USERNAME and role is None)
    )

def is_admin(request: Request) -> bool:
    username = request.session.get("username")
    role = request.session.get("role")
    return role == "admin" or (role is None and username == APP_USERNAME)


def require_login(request: Request, application: str = "commercial"):
    if not logged_in(request):
        if request.session.get("username"):
            request.session.clear()
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu.")
    if request.session.get("application", "commercial") != application:
        raise HTTPException(status_code=403, detail="Aplikasi ini tidak sesuai dengan sesi login.")
    if is_admin(request):
        return
    if request.session.get("role") != "user":
        raise HTTPException(status_code=403, detail="Akses hanya tersedia bagi Admin dan User.")
    username = request.session["username"]
    with db() as con:
        user = con.execute(
            "SELECT role FROM app_users WHERE username=%s", (username,)
        ).fetchone()
    if not user or user["role"] != "user":
        request.session.clear()
        raise HTTPException(status_code=401, detail="Akun tidak lagi aktif.")


def require_admin(request: Request):
    if not logged_in(request):
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu.")
    if request.session.get("application", "commercial") != "commercial":
        raise HTTPException(status_code=403, detail="Aplikasi ini tidak sesuai dengan sesi login.")
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="Akses khusus admin.")


def require_sph_admin(request: Request):
    require_login(request, "sph")
    if not is_admin(request):
        raise HTTPException(status_code=403, detail="Akses khusus admin.")


SPH_ROLES = {
    "sales": "Sales",
    "commercial_head": "Commercial Head",
    "director": "Direksi",
    "legal": "Legal",
}


def require_sph_access(request: Request):
    require_login(request, "sph")
    username = request.session["username"]
    with db() as con:
        user = con.execute(
            "SELECT role,sph_role FROM app_users WHERE username=%s", (username,)
        ).fetchone()
    if not user or (
        user["role"] != "admin"
        and (user["role"] != "user" or user.get("sph_role") not in SPH_ROLES)
    ):
        request.session.clear()
        raise HTTPException(status_code=403, detail="Akun ini tidak memiliki akses ke SPH CNG.")
    request.session["role"] = user["role"]
    request.session["sph_role"] = user.get("sph_role")
    return user


def require_sph_role(request: Request, role: str):
    user = require_sph_access(request)
    if user.get("sph_role") != role:
        raise HTTPException(
            status_code=403,
            detail=f"Tindakan ini hanya dapat dilakukan oleh {SPH_ROLES[role]}.",
        )
    return user


def require_home_access(request: Request):
    if not logged_in(request):
        if request.session.get("username"):
            request.session.clear()
        return
    if request.session.get("application", "commercial") != "commercial":
        raise HTTPException(status_code=403, detail="Aplikasi ini tidak sesuai dengan sesi login.")
    username = request.session["username"]
    role = request.session.get("role")
    if role == "admin" or (role is None and username == APP_USERNAME):
        return
    with db() as con:
        user = con.execute(
            "SELECT role FROM app_users WHERE username=%s", (username,)
        ).fetchone()
    if not user or user["role"] != "user":
        request.session.clear()
        raise HTTPException(status_code=401, detail="Akun tidak lagi aktif.")
    request.session["role"] = user["role"]


def hash_user_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_user_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$")
            if algorithm != "pbkdf2_sha256":
                return False
            expected = bytes.fromhex(digest_hex)
            supplied = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations),
            )
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(supplied, expected)
    supplied = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(supplied, stored_hash)


def norm(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def parse_number(value) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(" ", "")
    # Supports Indonesian 1.234,56 and common 1,234.56 formats.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        s = "".join(parts) if len(parts[-1]) == 3 and len(parts) > 1 else ".".join(parts)
    elif s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


AVERAGE_PRICE_MONTH_HEADERS = {
    1: {"jan", "januari"},
    2: {"feb", "februari"},
    3: {"mar", "maret"},
    4: {"apr", "april"},
    5: {"mei", "may"},
    6: {"jun", "juni"},
    7: {"jul", "juli"},
    8: {"agu", "agt", "agustus"},
    9: {"sep", "september"},
    10: {"okt", "oktober"},
    11: {"nov", "november"},
    12: {"des", "desember"},
}
AVERAGE_PRICE_CUSTOMER_ALIASES = {
    "ptciptalestariideanusa": "clin",
    "ptmitrakayagalvanize": "mkg",
    "ptoptimadhijaya": "optima",
    "concordindustry": "concord",
    "oaj": "optima",
    "optimaadhijaya": "optima",
    "adp": "aliadigital",
    "ami": "ateja",
    "altksomasami": "altinexmasami",
    "calbeeksobmi": "calbeeace",
    "cisfksorrs": "cisfrrs",
    "dic": "dicgrapichs",
    "gfranca": "gfrancaekek",
    "gfrsurcharge": "gfrsurcharge",
    "gfatom": "gfatom",
    "gfkulit": "gfkulit",
    "hci": "honchuan",
    "hli": "hligreenpower",
    "idpksoaae": "indoneptuneaae",
    "hskksogas": "hskgas",
    "indofood": "indofoodnsf",
    "ka": "karisma",
    "kgmksorrs": "kgmrrs",
    "niagagaram": "niagagaram",
    "pcimengger": "pcimengger",
    "pa": "cvpa",
    "spglobal": "suryapamenangglobal",
    "spksojes": "suryapamenangjes",
    "greenpulse": "greenpulse",
    "jiuqi": "jiuqi",
    "djarum": "djarum",
    "kimiafarmaksoineko": "kimiafarmima",
    "kimiafarmaima": "kimiafarmima",
    "ksn": "ksnmaja",
    "pentawiraksoren": "pentawiraren",
    "fjiksosalmah": "fjisbi",
    "fjiksbi": "fjisbi",
    "tongjiksogas": "tongtjigas",
    "winglokksoebm": "winglokebm",
}


def canonical_average_price_customer_key(value):
    key = norm(value)
    return AVERAGE_PRICE_CUSTOMER_ALIASES.get(key, key)


def parse_average_price_cell(value, unit_hint=""):
    text = str(value or "").strip()
    normalized_text = text.lower()
    if "$" in text or "usd" in normalized_text:
        price_unit = "USD_MMBTU"
    elif "rp" in normalized_text or "idr" in normalized_text:
        price_unit = "IDR_USD_MULTIPLIER"
    else:
        hint = str(unit_hint or "").lower()
        if "$" in hint or "usd" in hint:
            price_unit = "USD_MMBTU"
        elif "rp" in hint or "idr" in hint:
            price_unit = "IDR_USD_MULTIPLIER"
        else:
            price_unit = "USD_MMBTU"

    if not text or norm(text) in {"off", "na", "n/a"} or text in {"-", "—"}:
        return {"price_unit": price_unit, "price": 0.0, "active": False}

    number_text = re.sub(r"[^0-9,.]", "", text)
    if not number_text:
        return None
    if "," in number_text and "." in number_text:
        decimal_separator = "," if number_text.rfind(",") > number_text.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        number_text = number_text.replace(thousands_separator, "")
        number_text = number_text.replace(decimal_separator, ".")
    elif "," in number_text:
        decimal_places = len(number_text.rsplit(",", 1)[-1])
        number_text = number_text.replace(",", "." if decimal_places in {1, 2} else "")
    elif "." in number_text:
        decimal_places = len(number_text.rsplit(".", 1)[-1])
        if decimal_places == 3:
            number_text = number_text.replace(".", "")

    try:
        price = float(number_text)
    except ValueError:
        return None
    if not math.isfinite(price) or price <= 0:
        return None
    return {"price_unit": price_unit, "price": price, "active": True}


def parse_average_price_sheet_values(values, month):
    month_number = int(month.split("-")[1])
    month_headers = AVERAGE_PRICE_MONTH_HEADERS[month_number]
    header_row_index = None
    customer_column = None
    month_column = None
    unit_column = None

    for row_index, row in enumerate(values[:20]):
        normalized_headers = [norm(value) for value in row]
        customer_index = next(
            (
                index for index, value in enumerate(normalized_headers)
                if value in {"namacustomer", "customer", "customername"}
            ),
            None,
        )
        selected_month_index = next(
            (
                index for index, value in enumerate(normalized_headers)
                if value in month_headers
            ),
            None,
        )
        if customer_index is not None and selected_month_index is not None:
            header_row_index = row_index
            customer_column = customer_index
            month_column = selected_month_index
            unit_column = next(
                (
                    index for index, value in enumerate(normalized_headers)
                    if value in {"usdrp", "priceunit", "satuanharga"}
                ),
                None,
            )
            break

    if header_row_index is None:
        raise HTTPException(
            status_code=502,
            detail="Header customer dan bulan tidak ditemukan pada tab Harga Customer 2026.",
        )

    entries = []
    seen_customers = set()
    for row in values[header_row_index + 1:]:
        if customer_column >= len(row):
            continue
        customer = str(row[customer_column] or "").strip()
        if not customer:
            continue
        unit_hint = row[unit_column] if unit_column is not None and unit_column < len(row) else ""
        cell_value = row[month_column] if month_column < len(row) else ""
        parsed_price = parse_average_price_cell(cell_value, unit_hint)
        if parsed_price is None:
            continue
        customer_key = canonical_average_price_customer_key(customer)
        if customer_key in seen_customers:
            raise HTTPException(
                status_code=502,
                detail=f"Customer {customer} muncul lebih dari sekali pada sheet harga.",
            )
        seen_customers.add(customer_key)
        entries.append({
            "customer": customer,
            "price_unit": parsed_price["price_unit"],
            "price": parsed_price["price"],
            "active": parsed_price["active"],
        })
    return entries


def fetch_public_average_price_sheet_values():
    sheet_url = (
        f"https://docs.google.com/spreadsheets/d/{AVERAGE_PRICE_SHEET_ID}"
        f"/gviz/tq?tqx=out%3Acsv&gid={quote(AVERAGE_PRICE_SHEET_GID, safe='')}"
    )
    request = URLRequest(
        sheet_url,
        headers={"User-Agent": "CommercialSalesDashboard/1.0"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            csv_bytes = response.read(5_000_001)
    except (URLError, TimeoutError, OSError) as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Spreadsheet belum dapat dibaca oleh server. Bagikan akses Viewer kepada "
                "service account aplikasi, atau aktifkan akses publik baca-saja pada spreadsheet."
            ),
        ) from exc
    if len(csv_bytes) > 5_000_000:
        raise HTTPException(status_code=502, detail="Ukuran spreadsheet harga melebihi batas 5 MB.")
    try:
        text = csv_bytes.decode("utf-8-sig")
        return list(csv.reader(StringIO(text, newline="")))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise HTTPException(
            status_code=502,
            detail="Format CSV spreadsheet harga tidak valid.",
        ) from exc


def parse_date(value) -> Optional[str]:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if value is None:
        return None
    s = str(value).strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_sales_order_number(value):
    if value is None:
        return None
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not text or text in {"-", "—"}:
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            normalized = text.replace(".", "").replace(",", ".")
        else:
            normalized = text.replace(",", "")
    elif "," in text:
        parts = text.split(",")
        normalized = (
            "".join(parts)
            if len(parts) > 1 and len(parts[-1]) == 3
            else ".".join(parts)
        )
    elif "." in text:
        if text.count(".") > 1:
            normalized = text.replace(".", "")
        elif re.fullmatch(r"\d{1,3}\.\d{3}", text):
            normalized = text.replace(".", "")
        else:
            normalized = text
    else:
        normalized = text

    try:
        number = float(normalized)
    except ValueError as exc:
        raise ValueError(f"Nilai SO tidak valid: {value}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"Nilai SO harus berupa angka non-negatif: {value}")
    return number


def parse_sales_order_spreadsheet(csv_text):
    rows = list(csv.reader(StringIO(csv_text, newline="")))
    header_index = next(
        (
            index for index, row in enumerate(rows)
            if any(norm(value) == "date" for value in row)
        ),
        None,
    )
    if header_index is None or header_index + 1 >= len(rows):
        raise ValueError("Header tanggal pada sheet SO tidak ditemukan.")

    headers = rows[header_index]
    date_column = next(index for index, value in enumerate(headers) if norm(value) == "date")
    value_headers = rows[header_index + 1]
    customer_columns = [
        (index, str(name).strip())
        for index, name in enumerate(headers)
        if name
        and index != date_column
        and norm(name) not in {"revisi", "day", "total"}
        and index < len(value_headers)
        and norm(value_headers[index]) == "so"
    ]
    if not customer_columns:
        raise ValueError("Kolom customer dengan nilai SO tidak ditemukan.")

    records = {}
    for row_number, row in enumerate(rows[header_index + 2:], start=header_index + 3):
        date_value = row[date_column] if date_column < len(row) else ""
        populated_values = [
            row[index].strip()
            for index, _ in customer_columns
            if index < len(row) and row[index].strip()
        ]
        if not str(date_value or "").strip():
            if populated_values:
                raise ValueError(f"Tanggal kosong pada baris {row_number} sheet SO.")
            continue
        report_date = parse_date(date_value)
        if report_date is None:
            if populated_values:
                raise ValueError(f"Tanggal tidak valid pada baris {row_number} sheet SO.")
            continue

        day_records = []
        for column, customer in customer_columns:
            value = row[column] if column < len(row) else ""
            if not str(value or "").strip():
                continue
            try:
                so_value = parse_sales_order_number(value)
            except ValueError as exc:
                raise ValueError(
                    f"Nilai SO customer {customer} pada baris {row_number} tidak valid."
                ) from exc
            if so_value is not None:
                day_records.append({"customer": customer, "so": so_value})
        if day_records:
            records[report_date] = day_records

    if not records:
        raise ValueError("Sheet SO tidak memiliki data SO bertanggal.")
    return records


def parse_sales_order_gviz_response(response_text):
    match = re.search(
        r"google\.visualization\.Query\.setResponse\((.*)\);?\s*$",
        response_text,
        re.DOTALL,
    )
    if match is None:
        raise ValueError("Respons Google Sheets tidak valid.")

    try:
        response = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError("Respons Google Sheets tidak valid.") from exc

    if not isinstance(response, dict):
        raise ValueError("Respons Google Sheets tidak valid.")
    table = response.get("table")
    if response.get("status") != "ok" or not isinstance(table, dict):
        raise ValueError("Data SO Google Sheets tidak tersedia.")
    columns = table.get("cols")
    rows = table.get("rows")
    if (
        not isinstance(columns, list)
        or not columns
        or not all(isinstance(column, dict) for column in columns)
        or not isinstance(rows, list)
        or not all(isinstance(row, dict) for row in rows)
    ):
        raise ValueError("Struktur data SO Google Sheets tidak valid.")

    date_column = next(
        (
            index for index, column in enumerate(columns)
            if norm(column.get("label")) == "date"
        ),
        None,
    )
    customer_columns = []
    for index, column in enumerate(columns):
        label = str(column.get("label") or "").strip()
        customer_match = re.fullmatch(r"(.+?)\s+SO", label, re.IGNORECASE)
        if (
            customer_match
            and norm(label) != "totalso"
            and index != date_column
        ):
            customer_columns.append((index, customer_match.group(1).strip()))
    if date_column is None or not customer_columns:
        raise ValueError("Kolom tanggal atau customer pada sheet SO tidak ditemukan.")

    records = {}
    date_pattern = re.compile(r"Date\((\d{4}),(\d{1,2}),(\d{1,2})\)")
    for row_number, row in enumerate(rows, start=1):
        cells = row.get("c") or []
        date_cell = cells[date_column] if date_column < len(cells) else None
        date_value = date_cell.get("v") if isinstance(date_cell, dict) else None
        if isinstance(date_value, str):
            date_match = date_pattern.fullmatch(date_value)
            if date_match:
                try:
                    report_date = date(
                        int(date_match.group(1)),
                        int(date_match.group(2)) + 1,
                        int(date_match.group(3)),
                    ).isoformat()
                except ValueError as exc:
                    raise ValueError(
                        f"Tanggal tidak valid pada baris {row_number} sheet SO."
                    ) from exc
            else:
                report_date = parse_date(date_value)
        else:
            report_date = None

        day_records = []
        has_values = False
        for column, customer in customer_columns:
            cell = cells[column] if column < len(cells) else None
            value = cell.get("v") if isinstance(cell, dict) else None
            if value is None or value == "":
                continue
            has_values = True
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(
                    f"Nilai SO customer {customer} pada baris {row_number} tidak valid."
                )
            if not math.isfinite(value) or value < 0:
                raise ValueError(
                    f"Nilai SO customer {customer} pada baris {row_number} tidak valid."
                )
            day_records.append({"customer": customer, "so": float(value)})

        if report_date is None:
            if has_values:
                raise ValueError(f"Tanggal tidak valid pada baris {row_number} sheet SO.")
            continue
        if day_records:
            records[report_date] = day_records

    if not records:
        raise ValueError("Sheet SO tidak memiliki data SO bertanggal.")
    return records


def get_sales_order_data(refresh=False):
    now = time.monotonic()
    cached = _sales_order_cache["data"]
    if not refresh and cached is not None and now < _sales_order_cache["expires_at"]:
        return cached

    with _sales_order_lock:
        now = time.monotonic()
        cached = _sales_order_cache["data"]
        if not refresh and cached is not None and now < _sales_order_cache["expires_at"]:
            return cached

        url = (
            f"https://docs.google.com/spreadsheets/d/{SALES_ORDER_SHEET_ID}"
            f"/gviz/tq?tqx=out:json&gid={SALES_ORDER_SHEET_GID}"
        )
        request = URLRequest(url, headers={"User-Agent": "CommercialSalesDashboard/1.0"})
        try:
            with urlopen(request, timeout=20) as response:
                content = response.read(5_000_001)
        except (URLError, TimeoutError) as exc:
            raise HTTPException(
                status_code=502,
                detail="Sheet SO Google Sheets tidak dapat diakses. Coba lagi beberapa saat.",
            ) from exc
        if len(content) > 5_000_000:
            raise HTTPException(status_code=502, detail="Ukuran sheet SO melebihi batas 5 MB.")

        try:
            result = parse_sales_order_gviz_response(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Format data sheet SO tidak valid: {exc}",
            ) from exc

        _sales_order_cache["data"] = result
        _sales_order_cache["expires_at"] = time.monotonic() + SALES_ORDER_CACHE_SECONDS
        return result


def overlay_sales_order_forecast(
    sales_rows,
    customer_rows,
    sales_orders_by_date,
    start_date,
    end_date,
):
    customers_by_key = {}
    customer_lookup = {}
    for customer in customer_rows:
        key = str(customer["customer_key"])
        customers_by_key[key] = customer
        for candidate in (key, norm(customer["customer_name"])):
            if candidate:
                customer_lookup.setdefault(candidate, {})[key] = customer

    def resolve_customer(name):
        name_key = norm(name)
        matches = customer_lookup.get(name_key, {})
        if len(matches) == 1:
            return next(iter(matches.values()))
        if matches:
            return None
        base_name = re.sub(r"\s*\([^)]*\)\s*$", "", str(name)).strip()
        base_matches = customer_lookup.get(norm(base_name), {})
        return next(iter(base_matches.values())) if len(base_matches) == 1 else None

    enriched_by_key = {}
    dates_with_nonzero_actual = set()
    for row in sales_rows:
        enriched = dict(row)
        report_date = enriched.get("report_date", start_date)
        if isinstance(report_date, date):
            report_date = report_date.isoformat()
        enriched["report_date"] = str(report_date)
        enriched.setdefault("actual_is_forecast", False)
        if float(enriched.get("actual") or 0) != 0:
            dates_with_nonzero_actual.add(enriched["report_date"])
        enriched_by_key[(enriched["report_date"], str(enriched["customer_key"]))] = enriched

    unmapped = set()
    for report_date, orders in sales_orders_by_date.items():
        day = date.fromisoformat(report_date)
        if day < start_date or day > end_date:
            continue
        for order in orders:
            customer = resolve_customer(order["customer"])
            if customer is None:
                if order["so"] != 0:
                    unmapped.add(order["customer"])
                continue

            key = (report_date, str(customer["customer_key"]))
            existing = enriched_by_key.get(key)
            if existing is not None:
                existing["so"] = order["so"]
                if (
                    float(existing.get("actual") or 0) == 0
                    and report_date not in dates_with_nonzero_actual
                    and order["so"] > 0
                ):
                    existing["actual"] = order["so"]
                    existing["actual_is_forecast"] = True
                continue

            enriched_by_key[key] = {
                "report_date": report_date,
                "customer_key": customer["customer_key"],
                "customer_name": customer["customer_name"],
                "operator": customer["operator"],
                "so": order["so"],
                "actual": order["so"],
                "id": None,
                "manual_fob": False,
                "actual_is_forecast": True,
            }

    rows = list(enriched_by_key.values())
    for row in rows:
        row["so"] = float(row.get("so") or 0)
        row["actual"] = float(row.get("actual") or 0)
        row["diff"] = row["actual"] - row["so"]
    rows.sort(key=lambda row: (row["report_date"], row["operator"], row["customer_name"]))
    return rows, sorted(unmapped)


def detect_header(ws):
    aliases = {
        "date": {"tanggal", "date", "reportdate", "tanggalreport", "tgl"},
        "customer": {"customer", "namacustomer", "pelanggan", "customername", "nama"},
        "so": {"so", "salesorder", "targetso", "volumeSO".lower(), "qtyso"},
        "actual": {"actual", "realisasi", "penjualan", "actualsales", "qtyactual", "volumeactual"},
        "operator": {"operator", "lokasi", "plant", "area"},
    }
    # Scan first 30 rows because customer files often have title rows above the table.
    for row_idx in range(1, min(ws.max_row, 30) + 1):
        vals = [norm(c.value) for c in ws[row_idx]]
        found = {}
        for key, names in aliases.items():
            for col_idx, val in enumerate(vals, 1):
                if val in names:
                    found[key] = col_idx
                    break
        if "customer" in found and ("actual" in found or "so" in found):
            return row_idx, found
    return None, {}


def _cell_text(value) -> str:
    return str(value).strip() if value is not None else ""


def _is_total_label(value) -> bool:
    return norm(value) in {"total", "grandtotal", "subtotal", "subtot", "subtotals"}


def _operator_mappings_from_sheets(wb):
    """Read customer->operator mappings from worksheets named after operators."""
    mappings = {}
    excluded = {"customer", "namacustomer", "pelanggan", "nama", "tanggal", "date", "week", "so",
                "salesorder", "actual", "target", "diff", "selisih", "total", "subtotal", "subtot",
                "persentase", "percentage", "operator", "no", "nomor", "day", "hari"}
    for ws in wb.worksheets:
        op = ws.title.strip().upper()
        if op not in OPERATORS:
            continue
        header_row = None
        customer_col = None
        for r in range(1, min(ws.max_row, 30) + 1):
            for c in range(1, min(ws.max_column, 30) + 1):
                if norm(ws.cell(r, c).value) in {"customer", "namacustomer", "pelanggan", "customername"}:
                    header_row, customer_col = r, c
                    break
            if header_row:
                break
        if header_row and customer_col:
            for r in range(header_row + 1, ws.max_row + 1):
                name = _cell_text(ws.cell(r, customer_col).value)
                if not name or norm(name) in excluded or _is_total_label(name):
                    continue
                key = norm(name)
                mappings[key] = {"customer": name, "operator": op}
            continue
        # Fallback only for rows that look like customer records: text in first column,
        # plus at least one numeric value elsewhere on the same row.
        for r in range(1, ws.max_row + 1):
            name = _cell_text(ws.cell(r, 1).value)
            if not name or norm(name) in excluded or _is_total_label(name) or len(name) > 100:
                continue
            numeric_neighbor = any(isinstance(ws.cell(r, c).value, (int, float))
                                   for c in range(2, min(ws.max_column, 12) + 1))
            # Names that look like headings / date strings are not mapping candidates.
            if not numeric_neighbor or parse_date(name):
                continue
            key = norm(name)
            mappings[key] = {"customer": name, "operator": op}
    return mappings



def _mapping_from_operator_sheets(wb, con):
    """
    Gunakan sheet operator hanya untuk mendaftarkan customer baru.
    Jangan mengubah nama atau operator customer yang sudah ada di database.
    """
    mappings = _operator_mappings_from_sheets(wb)
    inserted = 0

    for key, mapping in mappings.items():
        result = con.execute(
            """
            INSERT IGNORE INTO customers
                (customer_key, customer_name, operator)
            VALUES (%s, %s, %s)
            """,
            (key, mapping["customer"], mapping["operator"]),
        )
        if result.rowcount > 0:
            inserted += 1

    return inserted



def daily_sales_customer_columns(ws):
    sub_values = [norm(ws.cell(4, column).value) for column in range(1, ws.max_column + 1)]
    actual_columns = []
    for column, value in enumerate(sub_values, start=1):
        if value not in {"actual", "realisasi", "penjualan", "actualsales"}:
            continue
        customer = _cell_text(ws.cell(3, column - 1).value) if column > 1 else ""
        if not customer:
            for heading_column in range(column - 1, 0, -1):
                customer = _cell_text(ws.cell(3, heading_column).value)
                if customer:
                    break
        if customer and not _is_total_label(customer):
            actual_columns.append((customer, column))
    return actual_columns, sub_values


def import_excel(path: Path, original_filename: str):
    # data_only=True is important: Daily Sales is formula-based, and Excel's saved
    # cached results are the actual reported figures we want to import.
    rows_read = rows_saved = 0
    now = datetime.now().isoformat(timespec="seconds")
    unmapped_customers = []
    mapping_saved = 0
    wb = None
    try:
        wb = load_workbook(path, data_only=True, read_only=False)
        daily = next((ws for ws in wb.worksheets if norm(ws.title) == "dailysales"), None)
        with db() as con:
            # If the uploaded workbook contains operator sheets, use them as a mapping source.
            mapping_saved = _mapping_from_operator_sheets(wb, con)
            if daily is not None:
                ws = daily
                # Horizontal layout used by the October 2026 master template:
                # row 3 = customer name, row 4 = TARGET/ACTUAL/SELISIH/PERSENTASE,
                # column B = date. Each customer occupies a four-column block.
                actual_cols, sub_values = daily_sales_customer_columns(ws)
                if not actual_cols:
                    raise ValueError("Sheet Daily Sales ditemukan, tetapi kolom ACTUAL horizontal tidak ditemukan pada baris 4.")
                unmapped_customers = list(dict.fromkeys(
                    customer for customer, _ in actual_cols
                    if find_operator(con, customer) not in CUSTOMER_ASSIGNMENTS
                ))
                if unmapped_customers:
                    names = ", ".join(unmapped_customers[:20])
                    remainder = len(unmapped_customers) - 20
                    suffix = f", dan {remainder} lainnya" if remainder > 0 else ""
                    raise ValueError(
                        "Impor dibatalkan. Operator tidak ditemukan otomatis untuk customer: "
                        f"{names}{suffix}. Tambahkan customer ke sheet operator pada file Excel "
                        "atau gunakan mapping yang sudah tersimpan."
                    )

                # Build SO lookup from the same template's TARGET columns, but never
                # replace a previously stored non-zero SO with a missing/zero formula result.
                target_cols = {}
                for c in range(1, ws.max_column + 1):
                    if sub_values[c - 1] not in {"target", "so", "salesorder"}:
                        continue
                    customer = ""
                    for hc in range(c, 0, -1):
                        candidate = _cell_text(ws.cell(3, hc).value)
                        if candidate:
                            customer = candidate
                            break
                    if customer and not _is_total_label(customer):
                        target_cols[norm(customer)] = c

                for r in range(5, ws.max_row + 1):
                    date_value = ws.cell(r, 2).value
                    if _is_total_label(date_value):
                        continue
                    report_date = parse_date(date_value)
                    if not report_date:
                        continue
                    for customer, actual_col in actual_cols:
                        actual_value = ws.cell(r, actual_col).value
                        # Do not create rows for blank cells. Explicit numeric zero is valid.
                        if actual_value is None or isinstance(actual_value, str) and not actual_value.strip():
                            continue
                        rows_read += 1
                        key = norm(customer)
                        op = find_operator(con, customer)
                        if op not in CUSTOMER_ASSIGNMENTS:
                            unmapped_customers.append(customer)
                            continue
                        existing = con.execute("SELECT so FROM sales WHERE report_date=%s AND customer_key=%s",
                                               (report_date, key)).fetchone()
                        so_value = None
                        tc = target_cols.get(key)
                        if tc:
                            candidate_so = ws.cell(r, tc).value
                            if candidate_so is not None and str(candidate_so).strip() != "":
                                so_value = parse_number(candidate_so)
                        # SO is sourced from the template if available; if this upload is
                        # a later actual-only file and template SO is absent, preserve DB SO.
                        if so_value is None:
                            so_value = float(existing["so"]) if existing else 0.0
                        actual = parse_number(actual_value)
                        con.execute("INSERT INTO sales(report_date,customer_key,so,actual,source_file,imported_at) "
                                    "VALUES(%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                                    "so=VALUES(so),actual=VALUES(actual),source_file=VALUES(source_file),imported_at=VALUES(imported_at)",
                                    (report_date, key, so_value, actual, original_filename, now))
                        rows_saved += 1
            else:
                # Retain compatibility with conventional vertical source tables.
                for ws in wb.worksheets:
                    header_row, cols = detect_header(ws)
                    if not header_row:
                        continue
                    for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
                        def val(key):
                            idx = cols.get(key)
                            return row[idx - 1] if idx and idx <= len(row) else None
                        customer = _cell_text(val("customer"))
                        if not customer or _is_total_label(customer):
                            continue
                        report_date = parse_date(val("date"))
                        if not report_date:
                            continue
                        rows_read += 1
                        op = str(val("operator") or "").strip().upper()
                        if op not in CUSTOMER_ASSIGNMENTS:
                            op = find_operator(con, customer)
                        if op not in CUSTOMER_ASSIGNMENTS:
                            unmapped_customers.append(customer)
                            continue
                        key = norm(customer)
                        con.execute("INSERT INTO customers(customer_key,customer_name,operator) VALUES(%s,%s,%s) "
                                    "ON DUPLICATE KEY UPDATE customer_name=VALUES(customer_name),operator=VALUES(operator)",
                                    (key, customer, op))
                        so = parse_number(val("so"))
                        actual = parse_number(val("actual"))
                        con.execute("INSERT INTO sales(report_date,customer_key,so,actual,source_file,imported_at) "
                                    "VALUES(%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                                    "so=VALUES(so),actual=VALUES(actual),source_file=VALUES(source_file),imported_at=VALUES(imported_at)",
                                    (report_date, key, so, actual, original_filename, now))
                        rows_saved += 1

            if unmapped_customers:
                unmapped_customers = list(dict.fromkeys(unmapped_customers))
                names = ", ".join(unmapped_customers[:20])
                remainder = len(unmapped_customers) - 20
                suffix = f", dan {remainder} lainnya" if remainder > 0 else ""
                raise ValueError(
                    "Impor dibatalkan. Operator tidak ditemukan otomatis untuk customer: "
                    f"{names}{suffix}. Tambahkan mapping ke database atau sheet operator pada file Excel."
                )

            if rows_saved == 0 and mapping_saved > 0:
                msg = f"Mapping operator berhasil dibaca: {mapping_saved} baris. Sekarang impor file yang memiliki sheet Daily Sales."
                con.execute("INSERT INTO import_history(filename,imported_at,rows_read,rows_saved,status,message) VALUES(%s,%s,%s,%s,%s,%s)",
                            (original_filename, now, 0, mapping_saved, "BERHASIL", msg))
                return {"rows_read": 0, "rows_saved": mapping_saved, "message": msg, "mapping_only": True}
            if rows_saved == 0:
                msg = "Tidak ada data yang berhasil diimpor. Pastikan sheet Daily Sales memiliki tanggal di kolom B, nama customer di baris 3, dan ACTUAL di baris 4; pastikan mapping operator sudah diimpor."
                raise ValueError(msg)
            msg = f"Impor selesai: {rows_saved} baris diperbarui." + (f" Mapping operator terbaca {mapping_saved} baris." if mapping_saved else "")
            con.execute("INSERT INTO import_history(filename,imported_at,rows_read,rows_saved,status,message) VALUES(%s,%s,%s,%s,%s,%s)",
                        (original_filename, now, rows_read, rows_saved, "BERHASIL", msg))
        return {"rows_read": rows_read, "rows_saved": rows_saved, "message": msg}
    except Exception as exc:
        failure_message = str(exc).strip() or "Impor gagal tanpa keterangan."
        with db() as con:
            con.execute(
                "INSERT INTO import_history(filename,imported_at,rows_read,rows_saved,status,message) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (original_filename, now, rows_read, 0, "GAGAL", failure_message),
            )
        raise
    finally:
        if wb is not None:
            wb.close()

def find_operator(con, customer: str) -> str:
    row = con.execute("SELECT operator FROM customers WHERE customer_key=%s", (norm(customer),)).fetchone()
    return row["operator"] if row else ""


def normalize_customer_mapping(customer_value, operator_value):
    customer = str(customer_value or "").strip()
    operator = str(operator_value or "").strip().upper()
    if not customer or operator not in CUSTOMER_ASSIGNMENTS:
        raise HTTPException(status_code=400, detail="Customer dan operator/status OFF wajib diisi dengan benar.")
    customer_key = norm(customer)
    if not customer_key or len(customer_key) > 191:
        raise HTTPException(status_code=400, detail="Nama customer tidak menghasilkan key yang valid.")
    return customer_key, customer, operator


@app.post("/api/login")
async def login(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format login tidak valid.")
    username = str(payload.get("username", ""))
    password = str(payload.get("password", ""))
    application = str(payload.get("application", "commercial"))
    if application not in {"commercial", "sph"}:
        raise HTTPException(status_code=400, detail="Pilihan aplikasi tidak valid.")
    with db() as con:
        row = con.execute(
            "SELECT password_hash,role,sph_role FROM app_users WHERE username=%s",
            (username,),
        ).fetchone()
    if (
        not row
        or row["role"] not in {"admin", "user"}
        or not verify_user_password(password, row["password_hash"])
    ):
        return JSONResponse({"detail": "Username atau password salah."}, status_code=401)
    if application == "sph" and row["role"] != "admin" and row.get("sph_role") not in SPH_ROLES:
        return JSONResponse(
            {"detail": "Akun ini belum diberi role SPH CNG oleh Admin."},
            status_code=403,
        )
    request.session.clear()
    request.session["username"] = username
    request.session["role"] = row["role"]
    request.session["application"] = application
    request.session["sph_role"] = row.get("sph_role")
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    if not logged_in(request):
        if request.session.get("username"):
            request.session.clear()
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu.")
    username = request.session["username"]
    with db() as con:
        user = con.execute(
            "SELECT role,sph_role FROM app_users WHERE username=%s", (username,)
        ).fetchone()
    if not user or user["role"] not in {"admin", "user"}:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Akun tidak lagi aktif.")
    request.session["role"] = user["role"]
    application = request.session.get("application", "commercial")
    if (
        application == "sph"
        and user["role"] != "admin"
        and user.get("sph_role") not in SPH_ROLES
    ):
        request.session.clear()
        raise HTTPException(status_code=403, detail="Akun ini tidak memiliki akses ke SPH CNG.")
    request.session["sph_role"] = user.get("sph_role")
    return {
        "username": username,
        "role": user["role"],
        "sphRole": user.get("sph_role"),
        "application": application,
    }


@app.get("/api/users")
def list_users(request: Request):
    require_admin(request)
    with db() as con:
        users = con.execute(
            "SELECT username,role,sph_role FROM app_users ORDER BY role,username"
        ).fetchall()
    return users


@app.get("/api/sph/users")
def list_sph_users(request: Request):
    require_sph_admin(request)
    with db() as con:
        users = con.execute(
            "SELECT username,role,sph_role FROM app_users WHERE role IN ('admin','user') ORDER BY role,username"
        ).fetchall()
    return users


@app.put("/api/sph/users/{username}/role")
async def update_sph_user_role(username: str, request: Request):
    require_sph_admin(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format role SPH tidak valid.")
    sph_role = payload.get("sphRole")
    if sph_role is not None and (
        not isinstance(sph_role, str) or sph_role not in SPH_ROLES
    ):
        raise HTTPException(status_code=400, detail="Role SPH tidak dikenal.")
    with db() as con:
        user = con.execute(
            "SELECT role FROM app_users WHERE username=%s", (username,)
        ).fetchone()
        if not user or user["role"] not in {"admin", "user"}:
            raise HTTPException(status_code=404, detail="Akun pengguna tidak ditemukan.")
        con.execute(
            "UPDATE app_users SET sph_role=%s WHERE username=%s",
            (sph_role, username),
        )
    return {"username": username, "sphRole": sph_role}


@app.post("/api/users")
async def create_user(request: Request):
    require_admin(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format akun tidak valid.")
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    role = str(payload.get("role", "user")).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,63}", username):
        raise HTTPException(
            status_code=400,
            detail="Username harus 3-64 karakter dan hanya boleh berisi huruf, angka, titik, garis bawah, atau tanda hubung.",
        )
    if not password or len(password) > 256:
        raise HTTPException(
            status_code=400,
            detail="Password akun harus terdiri dari 1-256 karakter.",
        )
    if role != "user":
        raise HTTPException(status_code=400, detail="Hanya akun User yang memerlukan login dan dapat dibuat.")
    with db() as con:
        existing = con.execute(
            "SELECT username FROM app_users WHERE username=%s", (username,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Username sudah digunakan.")
        con.execute(
            "INSERT INTO app_users(username,password_hash,role) VALUES(%s,%s,%s)",
            (username, hash_user_password(password), role),
        )
    return {"username": username, "role": role}


@app.put("/api/users/{username}/password")
async def update_user_password(username: str, request: Request):
    require_admin(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format password tidak valid.")
    password = str(payload.get("password", ""))
    if not password or len(password) > 256:
        raise HTTPException(
            status_code=400,
            detail="Password akun harus terdiri dari 1-256 karakter.",
        )
    with db() as con:
        user = con.execute(
            "SELECT role FROM app_users WHERE username=%s", (username,)
        ).fetchone()
        if not user or user["role"] != "user":
            raise HTTPException(status_code=404, detail="Akun pengguna tidak ditemukan.")
        con.execute(
            "UPDATE app_users SET password_hash=%s WHERE username=%s",
            (hash_user_password(password), username),
        )
    return {"username": username, "role": user["role"]}


@app.delete("/api/users/{username}")
def delete_user(username: str, request: Request):
    require_admin(request)
    if username == APP_USERNAME:
        raise HTTPException(status_code=400, detail="Akun admin utama tidak dapat dihapus.")
    with db() as con:
        user = con.execute(
            "SELECT role FROM app_users WHERE username=%s", (username,)
        ).fetchone()
        if not user or user["role"] not in {"user", "division"}:
            raise HTTPException(status_code=404, detail="Akun pengguna tidak ditemukan.")
        con.execute("DELETE FROM app_users WHERE username=%s", (username,))
    return {"ok": True}


SPH_STATUSES = {
    "draft": "Draft",
    "review": "Review",
    "approved": "Disetujui",
    "sent": "Terkirim",
    "negotiation": "Negosiasi",
    "customer_approved": "Disetujui Pelanggan",
    "pjbg": "Proses PJBG",
    "active": "Aktif",
}

SPH_GUARANTEES = {
    "Cash Deposit",
    "Bank Guarantee",
    "Parent Company Guarantee",
    "N/A",
}


def _sph_now():
    return datetime.now(ZoneInfo("Asia/Jakarta")).replace(tzinfo=None, microsecond=0)


def _sph_text(value, label, maximum=10000, required=False):
    if value is not None and not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{label} harus berupa teks.")
    text = str(value or "").strip()
    if required and not text:
        raise HTTPException(status_code=400, detail=f"{label} wajib diisi.")
    if len(text) > maximum:
        raise HTTPException(status_code=400, detail=f"{label} terlalu panjang.")
    return text


def _sph_validate_proposal(payload):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format SPH tidak valid.")
    customer_name = _sph_text(payload.get("customerName"), "Nama pelanggan", 255, True)
    customer_key = norm(customer_name)
    if not customer_key or len(customer_key) > 191:
        raise HTTPException(status_code=400, detail="Nama pelanggan tidak valid.")
    try:
        proposal_date = date.fromisoformat(str(payload.get("proposalDate", "")))
        numeric_fields = (
            payload.get("volumeMin"),
            payload.get("volumeMax"),
            payload.get("priceUsd"),
            payload.get("topPercent", 90),
        )
        if any(isinstance(value, bool) for value in numeric_fields):
            raise InvalidOperation
        volume_min, volume_max, price_usd, top_percent = (
            Decimal(str(value)) for value in numeric_fields
        )
        due_value = payload.get("dueDay", 20)
        years_value = payload.get("contractYears", 2)
        if isinstance(due_value, bool) or isinstance(years_value, bool):
            raise ValueError
        due_day, contract_years = int(due_value), int(years_value)
        if Decimal(str(due_value)) != due_day or Decimal(str(years_value)) != contract_years:
            raise ValueError
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Tanggal dan angka pada SPH harus valid.")
    if (
        not all(value.is_finite() for value in (volume_min, volume_max, price_usd, top_percent))
        or any(value.normalize().as_tuple().exponent < -2 for value in (
            volume_min, volume_max, price_usd, top_percent
        ))
        or volume_min <= 0
        or volume_max < volume_min
        or volume_max > Decimal("99999999999999.99")
        or price_usd <= 0
        or price_usd > Decimal("9999999999.99")
        or not 0 <= top_percent <= 100
        or not 1 <= due_day <= 28
        or not 1 <= contract_years <= 15
    ):
        raise HTTPException(status_code=400, detail="Nilai volume, harga, TOP, atau termin di luar batas.")
    guarantee_value = payload.get("guarantee", "Cash Deposit")
    if not isinstance(guarantee_value, str):
        raise HTTPException(status_code=400, detail="Jenis jaminan tidak valid.")
    guarantee = guarantee_value
    if guarantee not in SPH_GUARANTEES:
        raise HTTPException(status_code=400, detail="Jenis jaminan tidak valid.")
    exchange_clause = payload.get("exchangeClause", False)
    if not isinstance(exchange_clause, bool):
        raise HTTPException(status_code=400, detail="Klausul tukar menukar tidak valid.")
    return {
        "customer_key": customer_key,
        "customer_name": customer_name,
        "address_line1": _sph_text(payload.get("addressLine1"), "Alamat pelanggan", 2000),
        "address_line2": _sph_text(payload.get("addressLine2"), "Alamat pelanggan", 2000),
        "proposal_date": proposal_date,
        "volume_min": volume_min,
        "volume_max": volume_max,
        "price_usd": price_usd,
        "top_percent": top_percent,
        "guarantee": guarantee,
        "due_day": due_day,
        "exchange_clause": exchange_clause,
        "contract_years": contract_years,
        "reethau_obligations": _sph_text(payload.get("reethauObligations"), "Kewajiban Reethau"),
        "customer_obligations": _sph_text(payload.get("customerObligations"), "Kewajiban pelanggan"),
    }


def _sph_approval_route():
    return ["commercial_head"]


def _sph_proposal_row(con, proposal_id):
    return con.execute(
        "SELECT p.id,p.proposal_number AS number,p.customer_key,"
        "c.customer_name AS customerName,c.address_line1 AS addressLine1,"
        "c.address_line2 AS addressLine2,p.proposal_date AS proposalDate,"
        "p.volume_min AS volumeMin,p.volume_max AS volumeMax,p.price_usd AS priceUsd,"
        "p.status,p.version,p.top_percent AS topPercent,p.guarantee,p.due_day AS dueDay,"
        "p.exchange_clause AS exchangeClause,p.contract_years AS contractYears,"
        "p.reethau_obligations AS reethauObligations,"
        "p.customer_obligations AS customerObligations,p.approvals,p.sent_date AS sentDate,"
        "p.approved_at AS approvedAt,p.actual_volume AS actualVolume,p.created_by AS createdBy,"
        "p.updated_at AS updatedAt FROM sph_proposals p "
        "JOIN sph_customers c ON c.customer_key=p.customer_key WHERE p.id=%s",
        (proposal_id,),
    ).fetchone()


def _sph_proposal_json(row):
    if not row:
        return None
    result = dict(row)
    result["id"] = int(result["id"])
    result["version"] = int(result["version"])
    result["exchangeClause"] = bool(result["exchangeClause"])
    result["approvals"] = json.loads(result["approvals"] or "[]")
    for key in ("proposalDate", "sentDate", "approvedAt"):
        if result[key] is not None:
            result[key] = result[key].isoformat()
    if result["updatedAt"] is not None:
        result["updatedAt"] = result["updatedAt"].isoformat()
    for key in ("volumeMin", "volumeMax", "priceUsd", "topPercent", "actualVolume"):
        if result[key] is not None:
            result[key] = float(result[key])
    return result


def _sph_log(con, proposal_id, request, message):
    role = request.session.get("sph_role") or "admin"
    con.execute(
        "INSERT INTO sph_proposal_logs"
        "(proposal_id,actor_username,actor_role,message,created_at) "
        "VALUES(%s,%s,%s,%s,%s)",
        (proposal_id, request.session["username"], role, message, _sph_now()),
    )


def _sph_get_proposal(proposal_id):
    with db() as con:
        row = _sph_proposal_row(con, proposal_id)
        if not row:
            raise HTTPException(status_code=404, detail="SPH tidak ditemukan.")
        return _sph_proposal_json(row)


@app.get("/api/sph/proposals")
def sph_list_proposals(request: Request):
    require_sph_access(request)
    with db() as con:
        rows = con.execute(
            "SELECT p.id,p.proposal_number AS number,c.customer_name AS customerName,"
            "p.proposal_date AS proposalDate,p.volume_min AS volumeMin,"
            "p.volume_max AS volumeMax,p.price_usd AS priceUsd,p.top_percent AS topPercent,"
            "p.status,p.version,p.actual_volume AS actualVolume,p.updated_at AS updatedAt "
            "FROM sph_proposals p JOIN sph_customers c ON c.customer_key=p.customer_key "
            "ORDER BY p.updated_at DESC,p.id DESC"
        ).fetchall()
    proposals = []
    for row in rows:
        proposal = dict(row)
        proposal["id"] = int(proposal["id"])
        proposal["version"] = int(proposal["version"])
        proposal["proposalDate"] = proposal["proposalDate"].isoformat()
        proposal["updatedAt"] = proposal["updatedAt"].isoformat()
        for key in ("volumeMin", "volumeMax", "priceUsd", "topPercent", "actualVolume"):
            if proposal[key] is not None:
                proposal[key] = float(proposal[key])
        proposals.append(proposal)
    return proposals


@app.get("/api/sph/proposals/{proposal_id}")
def sph_get_proposal(proposal_id: int, request: Request):
    require_sph_access(request)
    proposal = _sph_get_proposal(proposal_id)
    with db() as con:
        logs = con.execute(
            "SELECT actor_username AS actor,actor_role AS actorRole,message,"
            "created_at AS createdAt FROM sph_proposal_logs "
            "WHERE proposal_id=%s ORDER BY id DESC",
            (proposal_id,),
        ).fetchall()
    proposal["history"] = [
        {
            **dict(log),
            "createdAt": log["createdAt"].isoformat(),
            "actorRoleLabel": SPH_ROLES.get(log["actorRole"], "Admin"),
        }
        for log in logs
    ]
    proposal["approvalRoute"] = _sph_approval_route()
    return proposal


@app.post("/api/sph/proposals")
async def sph_create_proposal(request: Request):
    require_sph_role(request, "sales")
    proposal = _sph_validate_proposal(await request.json())
    now = _sph_now()
    month_key = proposal["proposal_date"].strftime("%Y-%m")
    with db() as con:
        con.execute(
            "INSERT INTO sph_customers(customer_key,customer_name,address_line1,"
            "address_line2,created_by,created_at) VALUES(%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE customer_name=VALUES(customer_name),"
            "address_line1=VALUES(address_line1),address_line2=VALUES(address_line2)",
            (
                proposal["customer_key"], proposal["customer_name"],
                proposal["address_line1"], proposal["address_line2"],
                request.session["username"], now,
            ),
        )
        con.execute(
            "INSERT IGNORE INTO sph_sequences(month_key,next_value) VALUES(%s,0)",
            (month_key,),
        )
        sequence = con.execute(
            "SELECT next_value FROM sph_sequences WHERE month_key=%s FOR UPDATE",
            (month_key,),
        ).fetchone()["next_value"] + 1
        con.execute(
            "UPDATE sph_sequences SET next_value=%s WHERE month_key=%s",
            (sequence, month_key),
        )
        number = f"SPH-{proposal['proposal_date']:%Y-%m}-MKT-{sequence:03d}"
        cursor = con.execute(
            "INSERT INTO sph_proposals(proposal_number,customer_key,proposal_date,"
            "volume_min,volume_max,price_usd,status,version,top_percent,guarantee,"
            "due_day,exchange_clause,contract_years,reethau_obligations,"
            "customer_obligations,approvals,created_by,updated_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,'draft',0,%s,%s,%s,%s,%s,%s,%s,'[]',%s,%s)",
            (
                number, proposal["customer_key"], proposal["proposal_date"],
                proposal["volume_min"], proposal["volume_max"], proposal["price_usd"],
                proposal["top_percent"], proposal["guarantee"], proposal["due_day"],
                proposal["exchange_clause"], proposal["contract_years"],
                proposal["reethau_obligations"], proposal["customer_obligations"],
                request.session["username"], now,
            ),
        )
        proposal_id = cursor.lastrowid
        _sph_log(con, proposal_id, request, "Membuat draft SPH.")
    return _sph_get_proposal(proposal_id)


@app.put("/api/sph/proposals/{proposal_id}")
async def sph_update_proposal(proposal_id: int, request: Request):
    require_sph_role(request, "sales")
    proposal = _sph_validate_proposal(await request.json())
    now = _sph_now()
    with db() as con:
        current = _sph_proposal_row(con, proposal_id)
        if not current:
            raise HTTPException(status_code=404, detail="SPH tidak ditemukan.")
        if current["status"] == "active":
            raise HTTPException(status_code=409, detail="SPH berstatus Aktif tidak dapat diedit.")
        con.execute(
            "INSERT INTO sph_customers(customer_key,customer_name,address_line1,"
            "address_line2,created_by,created_at) VALUES(%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE customer_name=VALUES(customer_name),"
            "address_line1=VALUES(address_line1),address_line2=VALUES(address_line2)",
            (
                proposal["customer_key"], proposal["customer_name"],
                proposal["address_line1"], proposal["address_line2"],
                request.session["username"], now,
            ),
        )
        was_submitted = current["status"] != "draft"
        update_result = con.execute(
            "UPDATE sph_proposals SET customer_key=%s,proposal_date=%s,status='draft',"
            "volume_min=%s,volume_max=%s,price_usd=%s,top_percent=%s,guarantee=%s,"
            "due_day=%s,exchange_clause=%s,contract_years=%s,reethau_obligations=%s,"
            "customer_obligations=%s,version=version+%s,approvals='[]',"
            "approved_at=NULL,sent_date=NULL,updated_at=%s WHERE id=%s AND status <> 'active'",
            (
                proposal["customer_key"], proposal["proposal_date"],
                proposal["volume_min"], proposal["volume_max"], proposal["price_usd"],
                proposal["top_percent"], proposal["guarantee"], proposal["due_day"],
                proposal["exchange_clause"], proposal["contract_years"],
                proposal["reethau_obligations"], proposal["customer_obligations"],
                int(was_submitted), now, proposal_id,
            ),
        )
        if update_result.rowcount != 1:
            latest = _sph_proposal_row(con, proposal_id)
            if not latest:
                raise HTTPException(status_code=404, detail="SPH tidak ditemukan.")
            if latest["status"] == "active":
                raise HTTPException(status_code=409, detail="SPH berubah menjadi Aktif dan tidak dapat diedit.")
        message = (
            "Memperbarui SPH dan mengembalikan versi baru ke Draft."
            if was_submitted
            else "Memperbarui draft SPH."
        )
        _sph_log(con, proposal_id, request, message)
    return _sph_get_proposal(proposal_id)


@app.post("/api/sph/proposals/{proposal_id}/actions")
async def sph_proposal_action(proposal_id: int, request: Request):
    require_sph_access(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format tindakan tidak valid.")
    action = payload.get("action")
    if not isinstance(action, str):
        raise HTTPException(status_code=400, detail="Jenis tindakan tidak valid.")
    now = _sph_now()
    with db() as con:
        current_row = _sph_proposal_row(con, proposal_id)
        if not current_row:
            raise HTTPException(status_code=404, detail="SPH tidak ditemukan.")
        proposal = _sph_proposal_json(current_row)
        status = proposal["status"]
        sph_role = request.session.get("sph_role")
        allowed_role = None
        next_status = status
        message = None
        update = None
        if action == "submit" and status == "draft":
            allowed_role, next_status = "sales", "review"
            update = ("UPDATE sph_proposals SET status=%s,approvals='[]',updated_at=%s WHERE id=%s", (next_status, now, proposal_id))
            message = "Mengirim SPH untuk review."
        elif action in {"approve", "return"} and status == "review":
            approvals = proposal["approvals"]
            route = _sph_approval_route()
            if len(approvals) >= len(route):
                raise HTTPException(status_code=409, detail="Tahap persetujuan SPH sudah selesai.")
            allowed_role = route[len(approvals)]
            if action == "approve":
                approvals.append(allowed_role)
                next_status = "approved" if len(approvals) == len(route) else "review"
                update = (
                    "UPDATE sph_proposals SET status=%s,approvals=%s,approved_at=%s,updated_at=%s WHERE id=%s"
                    if next_status == "approved"
                    else "UPDATE sph_proposals SET status=%s,approvals=%s,updated_at=%s WHERE id=%s",
                    (
                        (next_status, json.dumps(approvals), now.date(), now, proposal_id)
                        if next_status == "approved"
                        else (next_status, json.dumps(approvals), now, proposal_id)
                    ),
                )
                message = f"Persetujuan {SPH_ROLES[allowed_role]} dicatat."
            else:
                next_status = "draft"
                update = (
                    "UPDATE sph_proposals SET status=%s,approvals='[]',updated_at=%s WHERE id=%s",
                    (next_status, now, proposal_id),
                )
                message = _sph_text(payload.get("reason"), "Alasan pengembalian", 2000, True)
                message = f"SPH dikembalikan ke draft: {message}"
        elif action == "mark_sent" and status == "approved":
            allowed_role, next_status = "sales", "sent"
            update = (
                "UPDATE sph_proposals SET status=%s,sent_date=%s,updated_at=%s WHERE id=%s",
                (next_status, now.date(), now, proposal_id),
            )
            message = "SPH dikirim kepada pelanggan."
        elif action in {"customer_approved", "negotiation"} and status == "sent":
            allowed_role = "sales"
            next_status = "customer_approved" if action == "customer_approved" else "negotiation"
            update = (
                "UPDATE sph_proposals SET status=%s,updated_at=%s WHERE id=%s",
                (next_status, now, proposal_id),
            )
            message = (
                "Pelanggan menyetujui SPH."
                if action == "customer_approved"
                else "Pelanggan meminta negosiasi."
            )
        elif action == "revise" and status == "negotiation":
            allowed_role, next_status = "sales", "draft"
            update = (
                "UPDATE sph_proposals SET status=%s,version=version+1,approvals='[]',"
                "approved_at=NULL,sent_date=NULL,updated_at=%s WHERE id=%s",
                (next_status, now, proposal_id),
            )
            message = "Membuat revisi SPH dari hasil negosiasi."
        elif action == "handoff_legal" and status == "customer_approved":
            allowed_role, next_status = "sales", "pjbg"
            update = (
                "UPDATE sph_proposals SET status=%s,updated_at=%s WHERE id=%s",
                (next_status, now, proposal_id),
            )
            message = "Dokumen diserahkan ke Legal untuk proses PJBG."
        elif action == "activate" and status == "pjbg":
            allowed_role, next_status = "legal", "active"
            update = (
                "UPDATE sph_proposals SET status=%s,updated_at=%s WHERE id=%s",
                (next_status, now, proposal_id),
            )
            message = "PJBG selesai dan pelanggan diaktifkan."
        elif action == "record_actual" and status == "active":
            allowed_role = "commercial_head"
            try:
                actual_raw = payload.get("actualVolume")
                if isinstance(actual_raw, bool):
                    raise InvalidOperation
                actual_volume = Decimal(str(actual_raw))
            except (InvalidOperation, TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Volume aktual harus berupa angka.")
            if (
                not actual_volume.is_finite()
                or actual_volume < 0
                or actual_volume > Decimal("99999999999999.99")
                or actual_volume.normalize().as_tuple().exponent < -2
            ):
                raise HTTPException(status_code=400, detail="Volume aktual tidak valid.")
            update = (
                "UPDATE sph_proposals SET actual_volume=%s,updated_at=%s WHERE id=%s",
                (actual_volume, now, proposal_id),
            )
            message = f"Mencatat volume aktual {actual_volume:g} MMBTU."
        else:
            raise HTTPException(status_code=409, detail="Tindakan tidak sesuai dengan status SPH.")
        if sph_role != allowed_role:
            raise HTTPException(
                status_code=403,
                detail=f"Tindakan ini hanya dapat dilakukan oleh {SPH_ROLES[allowed_role]}.",
            )
        con.execute(*update)
        _sph_log(con, proposal_id, request, message)
    return _sph_get_proposal(proposal_id)


@app.get("/api/sph/proposals/{proposal_id}/pdf")
def sph_proposal_pdf(proposal_id: int, request: Request):
    require_sph_access(request)
    proposal = _sph_get_proposal(proposal_id)
    with db() as con:
        _sph_log(con, proposal_id, request, "Mengunduh PDF SPH.")
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Generator PDF SPH belum tersedia.") from exc

    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=28 * mm, leftMargin=28 * mm,
        topMargin=35 * mm, bottomMargin=18 * mm,
        title=f"Surat Penawaran Harga {proposal['number']}",
        author="Reethau",
    )
    sph_pdf_logo = BASE_DIR / "static" / "reethau-sph.png"
    if not sph_pdf_logo.is_file():
        raise HTTPException(status_code=503, detail="Logo template PDF SPH tidak tersedia.")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="SphBody", parent=styles["BodyText"], fontName="Times-Roman",
        fontSize=9, leading=10.2, alignment=TA_LEFT, spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="SphSection", parent=styles["BodyText"], fontName="Times-Bold",
        fontSize=10, leading=12, textColor=colors.black,
        leftIndent=6 * mm,
        spaceBefore=5, spaceAfter=3, keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="SphIndented", parent=styles["BodyText"], fontName="Times-Roman",
        fontSize=9, leading=10.2, leftIndent=12 * mm, spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="SphList", parent=styles["BodyText"], fontName="Times-Roman",
        fontSize=9, leading=10.2, leftIndent=12 * mm, spaceAfter=1,
    ))
    styles.add(ParagraphStyle(
        name="SphTableHeader", parent=styles["BodyText"], fontName="Times-Bold",
        fontSize=9, leading=10, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="SphWatermark", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=28, textColor=colors.HexColor("#b94a48"),
    ))
    safe = lambda value: str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    def obligation_lines(value):
        lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
        return [
            Paragraph(f"{index}. {safe(line)}", styles["SphList"])
            for index, line in enumerate(lines, start=1)
        ] or [Paragraph("-", styles["SphBody"])]

    proposal_date = date.fromisoformat(proposal["proposalDate"])
    weekdays = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
    months = (
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    )
    date_label = (
        f"{weekdays[proposal_date.weekday()]}, {proposal_date.day} "
        f"{months[proposal_date.month - 1]} {proposal_date.year}"
    )
    address = ", ".join(
        part.strip().rstrip(",")
        for part in (proposal["addressLine1"], proposal["addressLine2"])
        if part.strip()
    )
    contract_year_words = {
        1: "Satu", 2: "Dua", 3: "Tiga", 4: "Empat", 5: "Lima",
        6: "Enam", 7: "Tujuh", 8: "Delapan", 9: "Sembilan",
        10: "Sepuluh", 11: "Sebelas", 12: "Dua Belas",
        13: "Tiga Belas", 14: "Empat Belas", 15: "Lima Belas",
    }
    def format_volume(value):
        formatted = f"{value:,.2f}".rstrip("0").rstrip(".")
        return formatted.replace(",", "\0").replace(".", ",").replace("\0", ".")

    volume_min = format_volume(proposal["volumeMin"])
    volume_max = format_volume(proposal["volumeMax"])
    price = f"{proposal['priceUsd']:.2f}"
    story = [
        Table(
            [
                ["No", ":", Paragraph(f"<b>{safe(proposal['number'])}</b>", styles["SphBody"])],
                ["Hari/Tanggal", ":", date_label],
            ],
            colWidths=[22 * mm, 4 * mm, document.width - 26 * mm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]),
        ),
        Spacer(1, 7 * mm),
        Paragraph("Kepada Yth.", styles["SphBody"]),
        Paragraph(f"<b>{safe(proposal['customerName'])}</b>", styles["SphBody"]),
        Paragraph(safe(address) or "-", styles["SphBody"]),
        Spacer(1, 3 * mm),
        Table(
            [[
                "Perihal",
                ":",
                Paragraph(
                    f"<b>Penawaran Harga Compressed Natural Gas (CNG) "
                    f"{safe(proposal['customerName'])}</b>",
                    styles["SphBody"],
                ),
            ]],
            colWidths=[22 * mm, 4 * mm, document.width - 26 * mm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]),
        ),
        Spacer(1, 3 * mm),
        Paragraph("Dengan hormat,", styles["SphBody"]),
        Paragraph(
            "Kami PT Reethau Cipta Energi merupakan perusahaan yang bergerak di bidang "
            "penyaluran Compressed Natural Gas (CNG) yang memiliki mother station "
            "berlokasi di Jalan Raya Setu, Bekasi, Jawa Barat. Dengan ini kami bermaksud "
            "memberikan penawaran harga CNG dengan kondisi penawaran sebagai berikut:",
            styles["SphBody"],
        ),
        Paragraph("A. Kondisi Penawaran", styles["SphSection"]),
        Paragraph(
            "Harga jual dan volume penggunaan Compressed Natural Gas (CNG) Direct "
            "sebagai berikut:",
            styles["SphIndented"],
        ),
    ]
    rows = [
        [
            Paragraph("Volume Min<br/>(MMBTU)", styles["SphTableHeader"]),
            Paragraph("Volume Max<br/>(MMBTU)", styles["SphTableHeader"]),
            Paragraph("USD/MMBTU", styles["SphTableHeader"]),
        ],
        [volume_min, volume_max, price],
    ]
    offer_table_width = 110 * mm
    table = Table(
        rows,
        colWidths=[offer_table_width / 3] * 3,
        repeatRows=1,
        hAlign="CENTER",
    )
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), .5, colors.HexColor("#9aa69e")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8cc63f")),
        ("FONTNAME", (0, 1), (-1, 1), "Times-Bold"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([
        Spacer(1, 2 * mm),
        table,
        Paragraph("B. Detail Penawaran", styles["SphSection"]),
        Paragraph(
            f"1. Masa kontrak {proposal['contractYears']} "
            f"({contract_year_words[proposal['contractYears']]}) tahun.",
            styles["SphIndented"],
        ),
        Paragraph("2. Garansi supply atau garansi kelangsungan pasokan CNG.", styles["SphIndented"]),
        Paragraph(
            "3. Perhitungan pemakaian CNG menggunakan metering milik "
            "PT Reethau Cipta Energi.",
            styles["SphIndented"],
        ),
        Paragraph(
            "4. Konversi sm3 menjadi MMBTU berdasarkan spesifikasi gas (nilai kalori) "
            "yang akan dikalkulasi setiap bulannya.",
            styles["SphIndented"],
        ),
        Paragraph(
            f"5. Menggunakan jaminan pembayaran berupa {safe(proposal['guarantee'])}.",
            styles["SphIndented"],
        ),
        Paragraph(
            f"6. Dikenakan TOP (Take or Pay) {proposal['topPercent']:g}% dari "
            "pengambilan minimum pemakaian.",
            styles["SphIndented"],
        ),
        Paragraph(
            f"7. Pembayaran dilakukan oleh Pihak Kedua paling lambat tanggal "
            f"{proposal['dueDay']} setiap bulannya ke rekening Pihak Pertama, "
            "PT Reethau Cipta Energi, PT Bank Mandiri No. Rekening "
            "167-000701735-2 (IDR).",
            styles["SphIndented"],
        ),
        Paragraph(
            "8. Sumber gas langsung dari PT Pertamina dan memiliki Izin Niaga Gas CNG.",
            styles["SphIndented"],
        ),
        Paragraph(
            "9. Harga gas dapat berubah berdasarkan eskalasi harga resmi dari "
            "pemerintah dan/atau sumber gas.",
            styles["SphIndented"],
        ),
        Paragraph("C. Kewajiban PT Reethau Cipta Energi", styles["SphSection"]),
        *obligation_lines(proposal["reethauObligations"]),
        Paragraph("D. Kewajiban Customer", styles["SphSection"]),
        *obligation_lines(proposal["customerObligations"]),
        Paragraph("E. Lain-lain", styles["SphSection"]),
        Paragraph("Draft Perjanjian Jual Beli Gas akan diberikan secara terpisah.", styles["SphIndented"]),
        PageBreak(),
        Paragraph(
            "Demikian surat penawaran harga Compressed Natural Gas (CNG) ini yang "
            "dapat kami sampaikan. Atas perhatian dan kerja sama Anda, kami ucapkan "
            "terima kasih.",
            styles["SphBody"],
        ),
        Spacer(1, 12 * mm),
        Table(
            [[Paragraph(
                "Hormat kami,<br/><b>PT Reethau Cipta Energi</b><br/><br/><br/><br/>"
                "<b>Commercial Head</b>",
                styles["SphBody"],
            )]],
            colWidths=[85 * mm],
            hAlign="LEFT",
        ),
    ])
    is_draft = proposal["status"] == "draft"

    def page_footer(canvas, _document):
        canvas.saveState()
        logo_width = 60 * mm
        logo_height = logo_width * 0.6
        canvas.drawImage(
            str(sph_pdf_logo),
            14 * mm,
            A4[1] - 2 * mm - logo_height,
            width=logo_width,
            height=logo_height,
            mask="auto",
        )
        if is_draft:
            canvas.setFillColor(colors.Color(.8, .2, .2, alpha=.12))
            canvas.setFont("Helvetica-Bold", 34)
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "DRAFT")
            canvas.rotate(-35)
            canvas.translate(-A4[0] / 2, -A4[1] / 2)
        canvas.setFillColor(colors.HexColor("#4f5551"))
        canvas.setFont("Helvetica-Bold", 5.5)
        canvas.drawString(20 * mm, 19 * mm, "OFFICE")
        canvas.setFont("Helvetica", 5.5)
        canvas.drawString(20 * mm, 16 * mm, "PT Reethau Cipta Energi")
        canvas.drawString(20 * mm, 13 * mm, "Jl. Darmawangsa Raya No. 8,")
        canvas.drawString(20 * mm, 10 * mm, "Kebayoran Baru - Jakarta Selatan 12160")
        canvas.drawCentredString(A4[0] * .64, 13 * mm, "P: +62 21 723 1238   |   +62 21 720 7130")
        canvas.drawRightString(A4[0] - 20 * mm, 13 * mm, "www.reethau.com")
        canvas.restoreState()

    document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    output.seek(0)
    filename = f"{proposal['number'].replace('/', '-')}.pdf"
    return StreamingResponse(
        output, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/import/preview")
async def preview_import(request: Request, file: UploadFile = File(...)):
    require_admin(request)
    filename = Path(file.filename or "upload.xlsx").name
    if Path(filename).suffix.lower() not in {".xlsx", ".xlsm"}:
        raise HTTPException(status_code=400, detail="Gunakan file Excel .xlsx atau .xlsm.")
    content = await file.read()
    if len(content) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 30 MB.")

    workbook = load_workbook(BytesIO(content), data_only=True, read_only=True)
    customers_by_key = {}
    try:
        daily = next((ws for ws in workbook.worksheets if norm(ws.title) == "dailysales"), None)
        sheet_mappings = _operator_mappings_from_sheets(workbook)
        if daily is not None:
            actual_columns, _ = daily_sales_customer_columns(daily)
            for customer, _ in actual_columns:
                key = norm(customer)
                mapped = sheet_mappings.get(key)
                customers_by_key.setdefault(key, {
                    "customer": customer,
                    "operator": mapped["operator"] if mapped else "",
                })
        else:
            for ws in workbook.worksheets:
                header_row, columns = detect_header(ws)
                if not header_row:
                    continue
                for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
                    customer_index = columns.get("customer")
                    customer = _cell_text(row[customer_index - 1]) if customer_index and customer_index <= len(row) else ""
                    if not customer or _is_total_label(customer):
                        continue
                    operator_index = columns.get("operator")
                    operator = str(row[operator_index - 1] or "").strip().upper() if operator_index and operator_index <= len(row) else ""
                    if operator not in CUSTOMER_ASSIGNMENTS:
                        operator = ""
                    key = norm(customer)
                    sheet_mapping = sheet_mappings.get(key)
                    if not operator and sheet_mapping:
                        operator = sheet_mapping["operator"]
                    customers_by_key.setdefault(key, {"customer": customer, "operator": operator})
                    if operator:
                        customers_by_key[key]["operator"] = operator
    finally:
        workbook.close()

    if not customers_by_key:
        raise HTTPException(status_code=400, detail="Nama customer tidak ditemukan pada sheet Daily Sales atau tabel Excel.")

    keys = list(customers_by_key)
    placeholders = ",".join(["%s"] * len(keys))
    with db() as con:
        mappings = con.execute(
            f"SELECT customer_key,operator FROM customers WHERE customer_key IN ({placeholders})",
            tuple(keys),
        ).fetchall()
    for mapping in mappings:
        customer = customers_by_key[mapping["customer_key"]]
        if not customer["operator"]:
            customer["operator"] = mapping["operator"]

    customers = list(customers_by_key.values())
    mapped_count = sum(bool(customer["operator"]) for customer in customers)
    return {"filename": filename, "customers": customers, "mapped_count": mapped_count}


@app.post("/api/import")
async def upload_excel(request: Request, file: UploadFile = File(...)):
    require_admin(request)
    filename = Path(file.filename or "upload.xlsx").name
    if Path(filename).suffix.lower() not in {".xlsx", ".xlsm"}:
        raise HTTPException(status_code=400, detail="Gunakan file Excel .xlsx atau .xlsm.")
    destination = INPUT_DIR / filename
    content = await file.read()
    if len(content) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 30 MB.")
    destination.write_bytes(content)
    try:
        result = import_excel(destination, filename)
        return {"ok": True, **result, "filename": filename}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/dates")
def dates(request: Request):
    require_home_access(request)
    with db() as con:
        rows = con.execute("SELECT DISTINCT report_date FROM sales ORDER BY report_date DESC").fetchall()
    return [r["report_date"].isoformat() for r in rows]


@app.post("/api/manual-fob-sales")
async def save_manual_fob_sale(request: Request):
    require_admin(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format data customer FOB tidak valid.")

    try:
        report_date = date.fromisoformat(str(payload.get("date", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Tanggal harus berformat YYYY-MM-DD.") from exc

    customer = str(payload.get("customer", "")).strip()
    operator = str(payload.get("operator", "")).strip().upper()
    if not customer or len(customer) > 150:
        raise HTTPException(status_code=400, detail="Nama customer FOB wajib diisi (maksimal 150 karakter).")
    if operator not in OPERATORS:
        raise HTTPException(status_code=400, detail="Pilihan MS tidak dikenal.")

    def validated_amount(field):
        value = payload.get(field)
        if isinstance(value, bool):
            raise HTTPException(status_code=400, detail=f"{field.upper()} harus berupa angka tidak negatif.")
        try:
            amount = float(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"{field.upper()} harus berupa angka tidak negatif.") from exc
        if not math.isfinite(amount) or amount < 0:
            raise HTTPException(status_code=400, detail=f"{field.upper()} harus berupa angka tidak negatif.")
        return amount

    so_value = validated_amount("so")
    actual_value = validated_amount("actual")
    customer_digest = hashlib.sha256(
        f"{report_date.isoformat()}|{operator.lower()}|{customer.casefold()}".encode("utf-8")
    ).hexdigest()
    customer_key = f"manualfob-{operator.lower()}-{customer_digest}"
    imported_at = datetime.now().isoformat(timespec="seconds")

    with db() as con:
        existing = con.execute(
            """
            SELECT s.customer_key
            FROM sales s
            JOIN customers c ON c.customer_key=s.customer_key
            WHERE s.report_date=%s AND s.source_file='manual-fob'
              AND c.operator=%s AND LOWER(c.customer_name)=LOWER(%s)
            LIMIT 1
            """,
            (report_date.isoformat(), operator, customer),
        ).fetchone()
        if existing:
            customer_key = existing["customer_key"]

        con.execute(
            "INSERT INTO customers(customer_key,customer_name,operator) VALUES(%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE customer_name=VALUES(customer_name),operator=VALUES(operator)",
            (customer_key, customer, operator),
        )
        con.execute(
            "INSERT INTO sales(report_date,customer_key,so,actual,source_file,imported_at) "
            "VALUES(%s,%s,%s,%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE so=VALUES(so),actual=VALUES(actual),"
            "source_file=VALUES(source_file),imported_at=VALUES(imported_at)",
            (report_date.isoformat(), customer_key, so_value, actual_value, "manual-fob", imported_at),
        )

    return {"ok": True, "diff": actual_value - so_value}


@app.put("/api/manual-fob-sales/{sale_id}")
async def update_manual_fob_sale(sale_id: int, request: Request):
    require_admin(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format data customer FOB tidak valid.")

    customer = str(payload.get("customer", "")).strip()
    operator = str(payload.get("operator", "")).strip().upper()
    if not customer or len(customer) > 150:
        raise HTTPException(status_code=400, detail="Nama customer FOB wajib diisi (maksimal 150 karakter).")
    if operator not in OPERATORS:
        raise HTTPException(status_code=400, detail="Pilihan MS tidak dikenal.")

    def validated_amount(field):
        value = payload.get(field)
        if isinstance(value, bool):
            raise HTTPException(status_code=400, detail=f"{field.upper()} harus berupa angka tidak negatif.")
        try:
            amount = float(value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"{field.upper()} harus berupa angka tidak negatif.") from exc
        if not math.isfinite(amount) or amount < 0:
            raise HTTPException(status_code=400, detail=f"{field.upper()} harus berupa angka tidak negatif.")
        return amount

    so_value = validated_amount("so")
    actual_value = validated_amount("actual")
    imported_at = datetime.now().isoformat(timespec="seconds")

    with db() as con:
        sale = con.execute(
            """
            SELECT s.report_date,s.customer_key
            FROM sales s
            JOIN customers c ON c.customer_key=s.customer_key
            WHERE s.id=%s AND s.source_file='manual-fob'
              AND c.customer_key LIKE 'manualfob-%%'
            """,
            (sale_id,),
        ).fetchone()
        if not sale:
            raise HTTPException(status_code=404, detail="Data FOB manual tidak ditemukan.")

        report_date = sale["report_date"]
        if isinstance(report_date, date):
            report_date = report_date.isoformat()
        digest = hashlib.sha256(
            f"{report_date}|{operator.lower()}|{customer.casefold()}".encode("utf-8")
        ).hexdigest()
        customer_key = f"manualfob-{operator.lower()}-{digest}"

        duplicate = con.execute(
            """
            SELECT id FROM sales
            WHERE report_date=%s AND customer_key=%s AND id<>%s
            """,
            (report_date, customer_key, sale_id),
        ).fetchone()
        if duplicate:
            raise HTTPException(
                status_code=409,
                detail="Customer FOB tersebut sudah ada pada tanggal dan MS ini.",
            )

        con.execute(
            "INSERT INTO customers(customer_key,customer_name,operator) VALUES(%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE customer_name=VALUES(customer_name),operator=VALUES(operator)",
            (customer_key, customer, operator),
        )
        con.execute(
            "UPDATE sales SET customer_key=%s,so=%s,actual=%s,imported_at=%s WHERE id=%s",
            (customer_key, so_value, actual_value, imported_at, sale_id),
        )
        if customer_key != sale["customer_key"]:
            con.execute(
                "DELETE FROM customers WHERE customer_key=%s "
                "AND NOT EXISTS (SELECT 1 FROM sales WHERE customer_key=%s)",
                (sale["customer_key"], sale["customer_key"]),
            )

    return {"ok": True, "diff": actual_value - so_value}


@app.delete("/api/manual-fob-sales/{sale_id}")
def delete_manual_fob_sale(sale_id: int, request: Request):
    require_admin(request)
    with db() as con:
        sale = con.execute(
            """
            SELECT s.customer_key
            FROM sales s
            JOIN customers c ON c.customer_key=s.customer_key
            WHERE s.id=%s AND s.source_file='manual-fob'
              AND c.customer_key LIKE 'manualfob-%%'
            """,
            (sale_id,),
        ).fetchone()
        if not sale:
            raise HTTPException(status_code=404, detail="Data FOB manual tidak ditemukan.")

        con.execute("DELETE FROM sales WHERE id=%s", (sale_id,))
        con.execute(
            "DELETE FROM customers WHERE customer_key=%s "
            "AND NOT EXISTS (SELECT 1 FROM sales WHERE customer_key=%s)",
            (sale["customer_key"], sale["customer_key"]),
        )

    return {"ok": True}


@app.get("/api/home-summary")
def home_summary(request: Request, month: str):
    require_home_access(request)
    try:
        month_start = date.fromisoformat(f"{month}-01")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Bulan harus berformat YYYY-MM.") from exc
    if len(month) != 7 or month_start.strftime("%Y-%m") != month:
        raise HTTPException(status_code=400, detail="Bulan harus berformat YYYY-MM.")

    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    month_end = next_month - timedelta(days=1)
    year_start = date(month_start.year, 1, 1)
    operators = (*OPERATORS, "OFF")

    with db() as con:
        rows = con.execute(
            """
            SELECT s.report_date, c.customer_name, c.operator,
                   s.customer_key, s.so, s.actual
            FROM sales s
            JOIN customers c ON c.customer_key = s.customer_key
            WHERE s.report_date BETWEEN %s AND %s
            ORDER BY s.report_date, c.operator, c.customer_key
            """,
            (year_start.isoformat(), month_end.isoformat()),
        ).fetchall()
        customer_rows = con.execute(
            "SELECT customer_key,customer_name,operator FROM customers"
        ).fetchall()
        manual_so_row = con.execute(
            "SELECT so FROM monthly_so_targets WHERE month_start=%s",
            (month_start.isoformat(),),
        ).fetchone()

    rows, _ = overlay_sales_order_forecast(
        rows,
        customer_rows,
        get_sales_order_data(),
        year_start,
        month_end,
    )

    def empty_totals():
        return {"so": 0.0, "actual": 0.0, "diff": 0.0, "customers": 0}

    def empty_operators():
        return {operator: empty_totals() for operator in operators}

    def add_values(target, row):
        so_value = float(row["so"] or 0)
        actual_value = float(row["actual"] or 0)
        target["so"] += so_value
        target["actual"] += actual_value
        target["diff"] += actual_value - so_value

    daily_data = {}
    monthly_data = {}
    year_operators = empty_operators()
    year_totals = empty_totals()
    daily_customers = {}
    daily_operator_customers = {}
    weekly_customers = {}
    weekly_operator_customers = {}
    monthly_customers = {}
    monthly_operator_customers = {}
    year_customers = set()
    year_operator_customers = {operator: set() for operator in operators}

    for row in rows:
        report_day = row["report_date"]
        if isinstance(report_day, str):
            report_day = date.fromisoformat(report_day)
        day_key = report_day.isoformat()
        month_key = report_day.strftime("%Y-%m")
        operator = row["operator"]
        customer_key = row["customer_key"]

        month_row = monthly_data.setdefault(
            month_key,
            {"totals": empty_totals(), "operators": empty_operators()},
        )
        add_values(month_row["totals"], row)
        add_values(month_row["operators"][operator], row)
        add_values(year_totals, row)
        add_values(year_operators[operator], row)

        is_active = operator != "OFF" and (
            float(row["so"] or 0) != 0 or float(row["actual"] or 0) != 0
        )
        if is_active:
            month_customer_set = monthly_customers.setdefault(month_key, set())
            month_customer_set.add(customer_key)
            monthly_operator_customers.setdefault((month_key, operator), set()).add(customer_key)
            year_customers.add(customer_key)
            year_operator_customers[operator].add(customer_key)

        if report_day >= month_start:
            monday = report_day - timedelta(days=report_day.weekday())
            week_key = monday.isoformat()
            day = daily_data.setdefault(
                day_key,
                {"totals": empty_totals(), "operators": empty_operators()},
            )
            add_values(day["totals"], row)
            add_values(day["operators"][operator], row)
            if is_active:
                daily_customers.setdefault(day_key, set()).add(customer_key)
                daily_operator_customers.setdefault((day_key, operator), set()).add(customer_key)
                weekly_customers.setdefault(week_key, set()).add(customer_key)
                weekly_operator_customers.setdefault((week_key, operator), set()).add(customer_key)

    def summary_record(values, **extra):
        return {
            **values,
            "achievement": values["actual"] / values["so"] * 100 if values["so"] else None,
            **extra,
        }

    days = []
    weekly_data = {}
    current_day = month_start
    while current_day <= month_end:
        key = current_day.isoformat()
        day_data = daily_data.get(key)
        totals = day_data["totals"] if day_data else empty_totals()
        totals["customers"] = len(daily_customers.get(key, set()))
        if day_data:
            for operator in operators:
                day_data["operators"][operator]["customers"] = len(
                    daily_operator_customers.get((key, operator), set())
                )
        days.append(summary_record(
            totals,
            date=key,
            has_data=day_data is not None,
            operators=day_data["operators"] if day_data else empty_operators(),
        ))
        monday = current_day - timedelta(days=current_day.weekday())
        week_key = monday.isoformat()
        week = weekly_data.setdefault(
            week_key,
            {"start_date": max(monday, month_start), "end_date": min(monday + timedelta(days=6), month_end),
             "totals": empty_totals(), "operators": empty_operators(), "has_data": False},
        )
        if day_data:
            week["has_data"] = True
            for operator in operators:
                add_values(week["operators"][operator], day_data["operators"][operator])
                add_values(week["totals"], day_data["operators"][operator])
        current_day += timedelta(days=1)

    weeks = [
        summary_record(
            {
                **week["totals"],
                "customers": len(weekly_customers.get(week_key, set())),
            },
            start_date=week["start_date"].isoformat(),
            end_date=week["end_date"].isoformat(),
            has_data=week["has_data"],
            operators={
                operator: {
                    **week["operators"][operator],
                    "customers": len(weekly_operator_customers.get((week_key, operator), set())),
                }
                for operator in operators
            },
        )
        for week_key, week in weekly_data.items()
    ]

    selected_month = monthly_data.get(
        month,
        {"totals": empty_totals(), "operators": empty_operators()},
    )
    selected_month["totals"]["customers"] = len(monthly_customers.get(month, set()))
    for operator in operators:
        selected_month["operators"][operator]["customers"] = len(
            monthly_operator_customers.get((month, operator), set())
        )
    months = []
    current_month = year_start
    while current_month <= month_start:
        month_key = current_month.strftime("%Y-%m")
        month_data = monthly_data.get(month_key)
        totals = dict(month_data["totals"]) if month_data else empty_totals()
        totals["customers"] = len(monthly_customers.get(month_key, set()))
        month_operators = {
            operator: {
                **month_data["operators"][operator],
                "customers": len(monthly_operator_customers.get((month_key, operator), set())),
            }
            for operator in operators
        } if month_data else empty_operators()
        months.append(summary_record(
            totals,
            month=month_key,
            has_data=month_data is not None,
            operators=month_operators,
        ))
        if current_month.month == 12:
            current_month = date(current_month.year + 1, 1, 1)
        else:
            current_month = date(current_month.year, current_month.month + 1, 1)

    return {
        "month": month,
        "start_date": month_start.isoformat(),
        "end_date": month_end.isoformat(),
        "days": days,
        "weeks": weeks,
        "month_summary": summary_record(
            selected_month["totals"],
            operators=selected_month["operators"],
            has_data=month in monthly_data,
            manual_so=(
                float(manual_so_row["so"])
                if manual_so_row is not None
                else None
            ),
        ),
        "year_summary": summary_record(
            {**year_totals, "customers": len(year_customers)},
            operators={
                operator: {
                    **year_operators[operator],
                    "customers": len(year_operator_customers[operator]),
                }
                for operator in operators
            },
            through_month=month,
            has_data=bool(monthly_data),
        ),
        "year_months": months,
    }


@app.get("/api/home-summary-range")
def home_summary_range(request: Request, start_date: str, end_date: str):
    require_home_access(request)
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Tanggal harus berformat YYYY-MM-DD.") from exc
    if start > end:
        raise HTTPException(status_code=400, detail="Tanggal awal tidak boleh melewati tanggal akhir.")
    operators = (*OPERATORS, "OFF")
    first_month = start.replace(day=1)
    last_month = end.replace(day=1)
    with db() as con:
        rows = con.execute(
            """
            SELECT s.report_date,c.customer_name,c.operator,s.customer_key,s.so,s.actual
            FROM sales s
            JOIN customers c ON c.customer_key=s.customer_key
            WHERE s.report_date BETWEEN %s AND %s
            ORDER BY s.report_date,c.operator,c.customer_key
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        target_rows = con.execute(
            "SELECT month_start,so FROM monthly_so_targets WHERE month_start BETWEEN %s AND %s",
            (first_month.isoformat(), last_month.isoformat()),
        ).fetchall()

    monthly_targets = {
        str(row["month_start"])[:7]: float(row["so"] or 0)
        for row in target_rows
    }
    report_total_so = 0.0
    report_total_actual = 0.0
    regional_volume_totals = {
        "JAWA BARAT": 0.0,
        "JAWA TENGAH": 0.0,
        "JAWA TIMUR": 0.0,
    }

    def empty_totals():
        return {"so": 0.0, "actual": 0.0, "diff": 0.0, "customers": 0}

    def empty_operators():
        return {operator: empty_totals() for operator in operators}

    def add_values(target, so, actual):
        target["so"] += so
        target["actual"] += actual
        target["diff"] += actual - so

    daily = {}
    monthly = {}
    active_customers = set()
    daily_active = {}
    monthly_active = {}
    daily_operator_active = {}
    monthly_operator_active = {}
    range_operator_active = {operator: set() for operator in operators}
    for row in rows:
        day = row["report_date"]
        if isinstance(day, str):
            day = date.fromisoformat(day)
        day_key = day.isoformat()
        month_key = day.strftime("%Y-%m")
        operator = row["operator"]
        so = float(row["so"] or 0)
        actual = float(row["actual"] or 0)
        report_total_so += so
        report_total_actual += actual
        customer_key = str(row["customer_key"] or "")
        region = REGION_BY_CUSTOMER.get(
            customer_key,
            REGION_BY_OPERATOR.get(str(operator or "").upper()),
        )
        if region is None:
            raise HTTPException(
                status_code=500,
                detail=f"Wilayah Actual belum dipetakan untuk operator {operator}.",
            )
        regional_volume_totals[region] += actual
        day_data = daily.setdefault(
            day_key,
            {"totals": empty_totals(), "operators": empty_operators()},
        )
        month_data = monthly.setdefault(
            month_key,
            {"totals": empty_totals(), "operators": empty_operators()},
        )
        add_values(day_data["totals"], so, actual)
        add_values(day_data["operators"][operator], so, actual)
        add_values(month_data["totals"], so, actual)
        add_values(month_data["operators"][operator], so, actual)
        if operator != "OFF" and (so != 0 or actual != 0):
            customer_key = row["customer_key"]
            active_customers.add(customer_key)
            daily_active.setdefault(day_key, set()).add(customer_key)
            monthly_active.setdefault(month_key, set()).add(customer_key)
            daily_operator_active.setdefault((day_key, operator), set()).add(customer_key)
            monthly_operator_active.setdefault((month_key, operator), set()).add(customer_key)
            range_operator_active[operator].add(customer_key)

    def summary_record(values, **extra):
        return {
            **values,
            "achievement": values["actual"] / values["so"] * 100 if values["so"] else None,
            **extra,
        }

    days = []
    for key in sorted(daily):
        data = daily[key]
        values = dict(data["totals"])
        values["customers"] = len(daily_active.get(key, set()))
        day_operators = data["operators"]
        for operator in operators:
            day_operators[operator]["customers"] = len(
                daily_operator_active.get((key, operator), set())
            )
        days.append(summary_record(
            values,
            date=key,
            has_data=True,
            operators=day_operators,
        ))

    year_months = []
    current_month = first_month
    while current_month <= last_month:
        key = current_month.strftime("%Y-%m")
        data = monthly.get(key)
        values = dict(data["totals"]) if data else empty_totals()
        values["customers"] = len(monthly_active.get(key, set()))
        month_operators = data["operators"] if data else empty_operators()
        for operator in operators:
            month_operators[operator]["customers"] = len(
                monthly_operator_active.get((key, operator), set())
            )
        year_months.append(summary_record(
            values,
            month=key,
            has_data=data is not None,
            operators=month_operators,
            manual_so=monthly_targets.get(key),
        ))
        if current_month.month == 12:
            current_month = date(current_month.year + 1, 1, 1)
        else:
            current_month = date(current_month.year, current_month.month + 1, 1)

    totals = empty_totals()
    for month_data in monthly.values():
        add_values(totals, month_data["totals"]["so"], month_data["totals"]["actual"])
    totals["customers"] = len(active_customers)
    operators_totals = empty_operators()
    for month_data in monthly.values():
        for operator in operators:
            add_values(
                operators_totals[operator],
                month_data["operators"][operator]["so"],
                month_data["operators"][operator]["actual"],
            )
    for operator in operators:
        operators_totals[operator]["customers"] = len(range_operator_active[operator])

    return {
        "month": start.strftime("%Y-%m"),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": days,
        "weeks": [],
        "month_summary": summary_record(
            totals,
            operators=operators_totals,
            has_data=bool(rows),
            manual_so=sum(float(row["so"] or 0) for row in target_rows) if target_rows else None,
        ),
        "summary_report": {
            "so": report_total_so,
            "actual": report_total_actual,
        },
        "regional_volumes": [
            {
                "region": region,
                "actual_sm3": actual_sm3,
            }
            for region, actual_sm3 in sorted(regional_volume_totals.items())
        ],
        "year_summary": summary_record(
            totals,
            operators=operators_totals,
            through_month=end.strftime("%Y-%m"),
            has_data=bool(rows),
        ),
        "year_months": year_months,
    }


def parse_month_start(month):
    if not isinstance(month, str):
        raise HTTPException(
            status_code=400,
            detail="Bulan harus berformat YYYY-MM.",
        )
    try:
        month_start = date.fromisoformat(f"{month}-01")
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail="Bulan harus berformat YYYY-MM.",
        ) from exc
    if len(month) != 7 or month_start.strftime("%Y-%m") != month:
        raise HTTPException(
            status_code=400,
            detail="Bulan harus berformat YYYY-MM.",
        )
    return month_start


@app.get("/api/monthly-so")
def get_monthly_so(request: Request, month: str):
    require_login(request)
    month_start = parse_month_start(month)
    with db() as con:
        row = con.execute(
            "SELECT so FROM monthly_so_targets WHERE month_start=%s",
            (month_start.isoformat(),),
        ).fetchone()
    return {
        "month": month,
        "so": float(row["so"]) if row is not None else None,
    }


@app.put("/api/monthly-so")
async def save_monthly_so(request: Request):
    require_admin(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format SO bulanan tidak valid.")

    month = payload.get("month")
    month_start = parse_month_start(month)
    so_value = payload.get("so")
    if isinstance(so_value, bool) or not isinstance(so_value, (int, float)):
        raise HTTPException(
            status_code=400,
            detail="Nilai SO bulanan harus berupa angka nol atau lebih.",
        )
    try:
        so_value = float(so_value)
    except OverflowError as exc:
        raise HTTPException(
            status_code=400,
            detail="Nilai SO bulanan harus berupa angka nol atau lebih.",
        ) from exc
    if not math.isfinite(so_value) or so_value < 0:
        raise HTTPException(
            status_code=400,
            detail="Nilai SO bulanan harus berupa angka nol atau lebih.",
        )

    updated_at = datetime.now().isoformat(timespec="seconds")
    with db() as con:
        con.execute(
            "INSERT INTO monthly_so_targets(month_start,so,updated_at) "
            "VALUES(%s,%s,%s) ON DUPLICATE KEY UPDATE "
            "so=VALUES(so),updated_at=VALUES(updated_at)",
            (month_start.isoformat(), so_value, updated_at),
        )
    return {"month": month, "so": so_value}


@app.get("/api/health")
def health():
    with db() as con:
        con.execute("SELECT 1").fetchone()
    return {"status": "ok", "database": "connected"}


def parse_issue_spreadsheet(csv_text):
    reader = csv.DictReader(StringIO(csv_text, newline=""))
    if not reader.fieldnames:
        raise ValueError("Spreadsheet Issue tidak memiliki header.")

    headers = {norm(header): header for header in reader.fieldnames if header}
    columns = {
        "customer": "customerpt",
        "customerPic": "customerpic",
        "date": "terjadinyakeluhan",
        "type": "jeniskeluhan",
        "rootCause": "rootcause",
        "impact": "dampakkeluhan",
        "supportingFiles": "filependukungfotovideosuratscreenshoot",
        "immediateAction": "tindakansegera",
        "latestUpdate": "updateterakhir",
        "correctiveAction": "tindakancorrective",
        "targetDate": "targetdate",
        "status": "status",
    }
    required = ("customer", "date", "type", "status")
    missing = [key for key in required if columns[key] not in headers]
    if missing:
        raise ValueError(
            "Header wajib spreadsheet Issue tidak ditemukan: "
            + ", ".join(missing)
        )

    issues = []
    try:
        for row_number, row in enumerate(reader, start=2):
            if not any(str(value or "").strip() for value in row.values()):
                continue
            values = {
                key: str(row.get(headers[header_key]) or "").strip()
                for key, header_key in columns.items()
                if header_key in headers
            }
            if not values["customer"]:
                raise ValueError(f"Customer kosong pada baris {row_number}.")
            try:
                issue_date = datetime.strptime(values["date"], "%d/%m/%Y").date()
            except ValueError:
                try:
                    issue_date = date.fromisoformat(values["date"])
                except ValueError as exc:
                    raise ValueError(
                        f"Tanggal keluhan tidak valid pada baris {row_number}."
                    ) from exc

            status_key = norm(values["status"])
            status = {
                "open": "Open",
                "inprogress": "In Progress",
                "onprogress": "In Progress",
                "monitoring": "In Progress",
                "closed": "Closed",
                "resolved": "Closed",
                "completed": "Closed",
                "selesai": "Closed",
            }.get(status_key, values["status"] or "Belum diisi")
            issues.append({
                "id": f"sheet-row-{row_number}",
                "date": issue_date.isoformat(),
                "customer": values["customer"],
                "customerPic": values["customerPic"],
                "type": values["type"],
                "rootCause": values["rootCause"],
                "impact": values["impact"],
                "supportingFiles": values["supportingFiles"],
                "immediateAction": values["immediateAction"],
                "latestUpdate": values["latestUpdate"],
                "correctiveAction": values["correctiveAction"],
                "targetDate": values["targetDate"],
                "status": status,
            })
    except csv.Error as exc:
        raise ValueError("Format CSV spreadsheet Issue tidak valid.") from exc

    issues.sort(key=lambda item: (item["date"], item["id"]), reverse=True)
    return issues


def fetch_issue_sheet_with_service_account():
    credential_path = Path(ISSUE_GOOGLE_SERVICE_ACCOUNT_FILE)
    if not credential_path.is_file() or credential_path.stat().st_size == 0:
        return None

    try:
        import json

        service_account_info = json.loads(credential_path.read_text(encoding="utf-8"))
        credentials = Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
    except (OSError, ValueError, TypeError, KeyError, GoogleAuthError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Kredensial Google service account tidak valid atau belum lengkap.",
        ) from exc

    session = AuthorizedSession(credentials)
    api_base = f"https://sheets.googleapis.com/v4/spreadsheets/{ISSUE_SHEET_ID}"
    try:
        metadata_response = session.get(
            f"{api_base}?fields=sheets(properties(sheetId,title))",
            timeout=15,
        )
        if metadata_response.status_code in {401, 403}:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Google Sheets API menolak akses service account. Aktifkan Google Sheets API "
                    "dan bagikan spreadsheet sebagai Viewer ke email client_email pada kredensial service account."
                ),
            )
        if metadata_response.status_code == 404:
            raise HTTPException(
                status_code=502,
                detail="Spreadsheet Issue tidak ditemukan. Periksa ISSUE_SHEET_ID.",
            )
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        if not isinstance(metadata, dict):
            raise HTTPException(
                status_code=502,
                detail="Respons metadata Google Sheets tidak valid.",
            )
        sheet = next(
            (
                item.get("properties", {})
                for item in metadata.get("sheets", [])
                if isinstance(item, dict)
                and str(item.get("properties", {}).get("sheetId")) == ISSUE_SHEET_GID
            ),
            None,
        )
        if not sheet or not sheet.get("title"):
            raise HTTPException(
                status_code=502,
                detail="Tab Google Sheets dengan ISSUE_SHEET_GID tersebut tidak ditemukan.",
            )

        encoded_range = quote(f"'{sheet['title']}'!A1:M5000", safe="")
        values_response = session.get(
            f"{api_base}/values/{encoded_range}",
            timeout=15,
        )
        if values_response.status_code in {401, 403}:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Service account tidak dapat membaca tab Issue. "
                    "Pastikan Google Sheets API aktif dan spreadsheet dibagikan dengan izin Viewer."
                ),
            )
        values_response.raise_for_status()
        values_payload = values_response.json()
        if not isinstance(values_payload, dict):
            raise HTTPException(
                status_code=502,
                detail="Respons data Google Sheets tidak valid.",
            )
        values = values_payload.get("values", [])
    except HTTPException:
        raise
    except RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail="Google Sheets API tidak merespons. Coba sinkronkan kembali beberapa saat lagi.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Google Sheets API mengembalikan respons JSON yang tidak valid.",
        ) from exc

    if not values:
        raise HTTPException(
            status_code=502,
            detail="Tab Google Sheets Issue kosong atau tidak memiliki header.",
        )

    csv_buffer = StringIO(newline="")
    csv_writer = csv.writer(csv_buffer)
    csv_writer.writerows(values)
    csv_text = csv_buffer.getvalue()
    if len(csv_text.encode("utf-8")) > 5_000_000:
        raise HTTPException(
            status_code=502,
            detail="Ukuran spreadsheet Issue melebihi batas 5 MB.",
        )
    return csv_text


def get_issue_spreadsheet_data(refresh=False):
    now = time.monotonic()
    cached = _issue_sheet_cache["data"]
    if not refresh and cached and now < _issue_sheet_cache["expires_at"]:
        return cached

    with _issue_sheet_lock:
        now = time.monotonic()
        cached = _issue_sheet_cache["data"]
        if not refresh and cached and now < _issue_sheet_cache["expires_at"]:
            return cached

        if not ISSUE_SHEET_ID or not ISSUE_SHEET_GID:
            raise HTTPException(
                status_code=500,
                detail="Konfigurasi sumber Google Sheets Issue belum lengkap.",
            )

        service_account_csv = fetch_issue_sheet_with_service_account()
        try:
            if service_account_csv is not None:
                csv_text = service_account_csv
            else:
                sheet_url = (
                    f"https://docs.google.com/spreadsheets/d/{ISSUE_SHEET_ID}"
                    f"/export?format=csv&gid={ISSUE_SHEET_GID}"
                )
                request = URLRequest(
                    sheet_url,
                    headers={"User-Agent": "CommercialSalesDashboard/1.0"},
                )
                try:
                    with urlopen(request, timeout=15) as response:
                        csv_bytes = response.read(5_000_001)
                except (URLError, TimeoutError, OSError) as exc:
                    raise HTTPException(
                        status_code=502,
                        detail=(
                            "Server tidak dapat membaca Google Sheets. "
                            "Akses Editor akun Anda tidak otomatis memberi akses kepada server. "
                            "Konfigurasikan service account dan bagikan spreadsheet kepadanya sebagai Viewer."
                        ),
                    ) from exc

                if len(csv_bytes) > 5_000_000:
                    raise HTTPException(
                        status_code=502,
                        detail="Ukuran spreadsheet Issue melebihi batas 5 MB.",
                    )
                csv_text = csv_bytes.decode("utf-8-sig")
            issues = parse_issue_spreadsheet(csv_text)
        except (UnicodeDecodeError, csv.Error, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Data Google Sheets Issue tidak valid: {exc}",
            ) from exc

        result = {
            "issues": issues,
            "syncedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        _issue_sheet_cache["data"] = result
        _issue_sheet_cache["expires_at"] = time.monotonic() + ISSUE_SHEET_CACHE_SECONDS
        return result


@app.get("/api/issues")
def list_issues(request: Request, refresh: bool = False):
    require_login(request)
    return get_issue_spreadsheet_data(refresh=refresh)


BUDGET_MONTHS = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)
BUDGET_CATEGORIES = {
    "1.1": ("Potensial", "potensialcustomer"),
    "1.2": ("Source", "pencarianevaluasisumbergas"),
    "1.3": ("Canvassing", "canvassing"),
    "2.1": ("Kunjungan Rutin Existing Customer", "kunjunganrutinexistingcustomer"),
    "3.1": ("Meeting Manajemen (HO)", "meetingmanajemenho"),
}


def parse_budget_amount(value):
    text = str(value or "").strip().replace("Rp", "").replace(" ", "")
    if not text:
        return 0.0
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", text):
        text = text.replace(".", "")
    try:
        amount = float(text)
    except ValueError as exc:
        raise ValueError(f"Nominal budget tidak valid: {value}") from exc
    if not math.isfinite(amount):
        raise ValueError(f"Nominal budget tidak valid: {value}")
    return amount


def parse_budget_spreadsheets(finance_csv, target_csv):
    finance_rows = list(csv.reader(StringIO(finance_csv, newline="")))
    target_rows = list(csv.reader(StringIO(target_csv, newline="")))
    if not finance_rows or not target_rows:
        raise ValueError("Spreadsheet Budget kosong atau tidak memiliki data.")

    finance_category_keys = {
        "kunjunganrutinexistingcustomer": "kunjunganrutinexistingcustomer",
        "meetingmanajemenho": "meetingmanajemenho",
        "canvassing": "canvassing",
        "potensialcustomer": "potensialcustomer",
        "pencarianevaluasisumbergas": "pencarianevaluasisumbergas",
    }
    finance_actuals = {}
    payment_type_index = next(
        (
            index for index, row in enumerate(finance_rows)
            if row and norm(row[0]) == "paymenttype"
        ),
        None,
    )
    if payment_type_index is None:
        raise ValueError("Bagian kategori pada tab Summary Finance tidak ditemukan.")

    expense_index = next(
        (
            index for index, row in enumerate(finance_rows)
            if row and norm(row[0]) == "pengeluaran"
        ),
        None,
    )
    monthly_expenses = None
    if expense_index is not None:
        for row in finance_rows[expense_index + 1:payment_type_index]:
            if not row or norm(row[0]) != "bulan":
                continue
            year_index = next(
                (index for index, value in enumerate(row) if str(value).strip() == "2026"),
                None,
            )
            if year_index is None:
                break
            expenses_by_month = {}
            for expense_row in finance_rows[expense_index + 1:payment_type_index]:
                if not expense_row:
                    continue
                month_index = next(
                    (
                        index for index, month_name in enumerate(BUDGET_MONTHS)
                        if norm(expense_row[0]) == norm(month_name)
                    ),
                    None,
                )
                if month_index is not None:
                    expenses_by_month[month_index] = parse_budget_amount(
                        expense_row[year_index] if year_index < len(expense_row) else ""
                    )
            if len(expenses_by_month) == len(BUDGET_MONTHS):
                monthly_expenses = [
                    expenses_by_month[index] for index in range(len(BUDGET_MONTHS))
                ]
            break
    if monthly_expenses is None:
        raise ValueError("Realisasi bulanan 2026 pada bagian PENGELUARAN tidak ditemukan.")

    for row in finance_rows[payment_type_index + 1:]:
        if not row or norm(row[0]) == "area":
            break
        category_key = finance_category_keys.get(norm(row[0]))
        if category_key:
            finance_actuals[category_key] = [
                parse_budget_amount(row[index] if index < len(row) else "")
                for index in range(1, 13)
            ]

    header_index = next(
        (
            index for index, row in enumerate(target_rows)
            if len(row) > 5 and norm(row[0]) == "workplan" and norm(row[2]) == "listcost"
        ),
        None,
    )
    if header_index is None:
        raise ValueError("Header WORK PLAN/LIST COST pada sheet target tidak ditemukan.")

    target_categories = {}
    for row in target_rows[header_index + 1:]:
        if len(row) <= 17:
            continue
        work_plan = str(row[2] or "").strip()
        match = re.match(r"(\d+\.\d+)\b", work_plan)
        if not match:
            continue
        category = BUDGET_CATEGORIES.get(match.group(1))
        if not category:
            continue
        label, finance_key = category
        target_categories[label] = {
            "finance_key": finance_key,
            "targets": [parse_budget_amount(row[6 + index]) for index in range(12)],
        }

    if not target_categories:
        raise ValueError("Baris target kategori Budget tidak ditemukan pada sheet target.")

    month_names = BUDGET_MONTHS
    records = []
    for label, category in target_categories.items():
        actuals = finance_actuals.get(category["finance_key"], [0.0] * 12)
        for month_index, month_name in enumerate(month_names):
            records.append({
                "month": f"2026-{month_index + 1:02d}",
                "month_name": month_name,
                "category": label,
                "target": category["targets"][month_index],
                "actual": actuals[month_index],
            })

    return {
        "months": [
            {
                "value": f"2026-{index + 1:02d}",
                "label": f"{month} 2026",
                "actual": monthly_expenses[index],
            }
            for index, month in enumerate(month_names)
        ],
        "records": records,
        "syncedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def fetch_budget_spreadsheets_with_service_account():
    credential_path = Path(ISSUE_GOOGLE_SERVICE_ACCOUNT_FILE)
    if not credential_path.is_file() or credential_path.stat().st_size == 0:
        return None

    try:
        service_account_info = json.loads(credential_path.read_text(encoding="utf-8"))
        credentials = Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
    except (OSError, ValueError, TypeError, KeyError, GoogleAuthError) as exc:
        raise HTTPException(
            status_code=500,
            detail="Kredensial Google service account tidak valid atau belum lengkap.",
        ) from exc

    session = AuthorizedSession(credentials)
    api_base = f"https://sheets.googleapis.com/v4/spreadsheets/{ISSUE_SHEET_ID}"
    try:
        metadata_response = session.get(
            f"{api_base}?fields=sheets(properties(sheetId,title))",
            timeout=15,
        )
        if metadata_response.status_code in {401, 403}:
            raise HTTPException(
                status_code=502,
                detail="Google Sheets API menolak akses service account. Pastikan spreadsheet dibagikan dengan izin Viewer.",
            )
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        sheets = metadata.get("sheets", []) if isinstance(metadata, dict) else []
        finance_sheet = next(
            (
                item.get("properties", {})
                for item in sheets
                if isinstance(item, dict)
                and norm(item.get("properties", {}).get("title")) == norm(BUDGET_FINANCE_SHEET_TITLE)
            ),
            None,
        )
        target_sheet = next(
            (
                item.get("properties", {})
                for item in sheets
                if isinstance(item, dict)
                and str(item.get("properties", {}).get("sheetId")) == BUDGET_TARGET_SHEET_GID
            ),
            None,
        )
        if not finance_sheet or not target_sheet:
            raise HTTPException(
                status_code=502,
                detail="Tab Summary Finance atau sheet target (GID 737662524) tidak ditemukan.",
            )

        def fetch_values(sheet, cell_range):
            encoded_range = quote(f"'{sheet['title']}'!{cell_range}", safe="")
            response = session.get(f"{api_base}/values/{encoded_range}", timeout=15)
            if response.status_code in {401, 403}:
                raise HTTPException(
                    status_code=502,
                    detail="Service account tidak dapat membaca tab Budget. Pastikan izin Viewer tersedia.",
                )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("values", []), list):
                raise HTTPException(
                    status_code=502,
                    detail="Respons data Google Sheets Budget tidak valid.",
                )
            return payload.get("values", [])

        return (
            fetch_values(finance_sheet, "A1:M120"),
            fetch_values(target_sheet, "A1:AG120"),
        )
    except HTTPException:
        raise
    except RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail="Google Sheets API tidak merespons. Coba sinkronkan kembali beberapa saat lagi.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Google Sheets API mengembalikan respons JSON yang tidak valid.",
        ) from exc


def rows_to_csv(rows):
    buffer = StringIO(newline="")
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue()


def fetch_public_budget_sheet(sheet_name=None, sheet_gid=None):
    if sheet_gid:
        sheet_query = f"gid={quote(sheet_gid, safe='')}"
    else:
        sheet_query = f"sheet={quote(sheet_name or '', safe='')}"
    sheet_url = (
        f"https://docs.google.com/spreadsheets/d/{ISSUE_SHEET_ID}"
        f"/gviz/tq?tqx=out%3Acsv&{sheet_query}"
    )
    request = URLRequest(
        sheet_url,
        headers={"User-Agent": "CommercialSalesDashboard/1.0"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            csv_bytes = response.read(5_000_001)
    except (URLError, TimeoutError, OSError) as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Server tidak dapat membaca Google Sheets Budget. "
                "Konfigurasikan service account dan bagikan spreadsheet kepadanya sebagai Viewer."
            ),
        ) from exc
    if len(csv_bytes) > 5_000_000:
        raise HTTPException(status_code=502, detail="Ukuran spreadsheet Budget melebihi batas 5 MB.")
    return csv_bytes.decode("utf-8-sig")


def get_budget_spreadsheet_data(refresh=False):
    now = time.monotonic()
    cached = _budget_cache["data"]
    if not refresh and cached and now < _budget_cache["expires_at"]:
        return cached

    with _budget_lock:
        now = time.monotonic()
        cached = _budget_cache["data"]
        if not refresh and cached and now < _budget_cache["expires_at"]:
            return cached

        service_account_data = fetch_budget_spreadsheets_with_service_account()
        if service_account_data is None:
            finance_csv = fetch_public_budget_sheet(BUDGET_FINANCE_SHEET_TITLE)
            target_csv = fetch_public_budget_sheet(sheet_gid=BUDGET_TARGET_SHEET_GID)
        else:
            finance_csv = rows_to_csv(service_account_data[0])
            target_csv = rows_to_csv(service_account_data[1])

        try:
            result = parse_budget_spreadsheets(finance_csv, target_csv)
        except (csv.Error, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Data Google Sheets Budget tidak valid: {exc}",
            ) from exc

        _budget_cache["data"] = result
        _budget_cache["expires_at"] = time.monotonic() + BUDGET_CACHE_SECONDS
        return result


@app.get("/api/budget")
def get_budget(request: Request, refresh: bool = False):
    require_login(request)
    return get_budget_spreadsheet_data(refresh=refresh)


def complaint_record(row):
    report_date = row["report_date"]
    status_changed_at = row["status_changed_at"]
    return {
        "id": row["id"],
        "date": report_date.isoformat() if isinstance(report_date, date) else str(report_date),
        "customer": row["customer"],
        "summary": row["summary"],
        "followUp": row["follow_up"],
        "type": row["complaint_type"],
        "priority": row["priority"],
        "status": row["status"],
        "statusChangedAt": (
            status_changed_at.isoformat(timespec="seconds")
            if isinstance(status_changed_at, datetime)
            else status_changed_at
        ),
        "resolution": row["resolution"],
        "updatedAt": row["updated_at"],
    }


def normalize_complaint(
    payload,
    preserve_updated_at=False,
):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format data complain tidak valid.")

    try:
        report_date = date.fromisoformat(str(payload.get("date", "")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Tanggal complain harus berformat YYYY-MM-DD.") from exc

    customer = str(payload.get("customer", "")).strip()
    summary = str(payload.get("summary", "")).strip()
    follow_up = str(payload.get("followUp", "")).strip()
    complaint_type = str(payload.get("type", "")).strip()
    priority = str(payload.get("priority", "")).strip()
    status = str(payload.get("status", "")).strip()
    resolution = str(payload.get("resolution", "")).strip()

    if not customer or len(customer) > 255 or not summary:
        raise HTTPException(status_code=400, detail="Nama customer dan ringkasan complain wajib diisi.")
    if complaint_type not in COMPLAINT_TYPES | LEGACY_COMPLAINT_TYPES:
        raise HTTPException(status_code=400, detail="Jenis complain tidak dikenal.")
    if priority not in {"Normal", "Tinggi", "Rendah"}:
        raise HTTPException(status_code=400, detail="Prioritas complain tidak dikenal.")
    if status not in {"Open", "Closed", "Monitoring"}:
        raise HTTPException(status_code=400, detail="Status complain tidak dikenal.")

    updated_at = datetime.now().isoformat(timespec="seconds")
    status_changed_at = None
    if status == "Closed":
        closing_date = str(payload.get("statusChangedAt", "")).strip()
        try:
            parsed_closing_date = date.fromisoformat(closing_date)
            if parsed_closing_date.isoformat() != closing_date:
                raise ValueError("Closing date must use YYYY-MM-DD.")
            status_changed_at = parsed_closing_date.isoformat()
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Tanggal Closed wajib diisi dan harus berformat YYYY-MM-DD.",
            ) from exc
    if preserve_updated_at:
        legacy_updated_at = str(payload.get("updatedAt", "")).strip()
        if legacy_updated_at:
            try:
                updated_at = datetime.fromisoformat(legacy_updated_at).isoformat(timespec="seconds")
            except ValueError:
                pass
        legacy_status_changed_at = (
            str(payload.get("statusChangedAt", "")).strip()
            if status == "Closed"
            else ""
        )
        if status == "Closed" and legacy_status_changed_at:
            try:
                status_changed_at = datetime.fromisoformat(
                    legacy_status_changed_at
                ).isoformat(timespec="seconds")
            except ValueError:
                status_changed_at = updated_at
        elif status == "Closed":
            status_changed_at = updated_at

    return (
        report_date.isoformat(),
        customer,
        summary,
        follow_up,
        complaint_type,
        priority,
        status,
        status_changed_at,
        resolution,
        updated_at,
    )


@app.get("/api/complaints")
def list_complaints(request: Request):
    require_home_access(request)
    if not is_admin(request) and request.session.get("role") != "user":
        with db() as con:
            rows = con.execute(
                "SELECT report_date,status,complaint_type FROM complaints "
                "ORDER BY report_date DESC,id DESC"
            ).fetchall()
        return [
            {
                "date": row["report_date"].isoformat()
                if isinstance(row["report_date"], date)
                else str(row["report_date"]),
                "status": row["status"],
                "type": row["complaint_type"],
            }
            for row in rows
        ]
    with db() as con:
        rows = con.execute(
            "SELECT id,report_date,customer,summary,follow_up,complaint_type,priority,status,"
            "status_changed_at,resolution,updated_at "
            "FROM complaints ORDER BY report_date DESC,id DESC"
        ).fetchall()
    return [complaint_record(row) for row in rows]


@app.post("/api/complaints")
async def create_complaint(request: Request):
    require_admin(request)
    fields = normalize_complaint(await request.json())
    with db() as con:
        cursor = con.execute(
            "INSERT INTO complaints(report_date,customer,summary,follow_up,complaint_type,priority,status,"
            "status_changed_at,resolution,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            fields,
        )
        row = con.execute(
            "SELECT id,report_date,customer,summary,follow_up,complaint_type,priority,status,"
            "status_changed_at,resolution,updated_at "
            "FROM complaints WHERE id=%s",
            (cursor.lastrowid,),
        ).fetchone()
    return complaint_record(row)


@app.put("/api/complaints/{complaint_id}")
async def update_complaint(complaint_id: int, request: Request):
    require_admin(request)
    if complaint_id < 1:
        raise HTTPException(status_code=400, detail="ID complain tidak valid.")
    with db() as con:
        current = con.execute(
            "SELECT id FROM complaints WHERE id=%s",
            (complaint_id,),
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="Complain tidak ditemukan.")
        fields = normalize_complaint(await request.json())
        cursor = con.execute(
            "UPDATE complaints SET report_date=%s,customer=%s,summary=%s,follow_up=%s,complaint_type=%s,"
            "priority=%s,status=%s,status_changed_at=%s,resolution=%s,updated_at=%s WHERE id=%s",
            (*fields, complaint_id),
        )
        row = con.execute(
            "SELECT id,report_date,customer,summary,follow_up,complaint_type,priority,status,"
            "status_changed_at,resolution,updated_at "
            "FROM complaints WHERE id=%s",
            (complaint_id,),
        ).fetchone()
    return complaint_record(row)


@app.post("/api/complaints/legacy-import")
async def import_legacy_complaints(request: Request):
    require_admin(request)
    payload = await request.json()
    complaints = payload.get("complaints") if isinstance(payload, dict) else None
    if not isinstance(complaints, list) or len(complaints) > 5000:
        raise HTTPException(status_code=400, detail="Data complain lama harus berupa daftar maksimal 5000 baris.")
    fields = [normalize_complaint(item, preserve_updated_at=True) for item in complaints]
    imported = 0
    skipped = 0
    with db() as con:
        for (
            report_date,
            customer,
            summary,
            follow_up,
            complaint_type,
            priority,
            status,
            status_changed_at,
            resolution,
            updated_at,
        ) in fields:
            existing = con.execute(
                "SELECT id FROM complaints WHERE report_date=%s AND customer=%s AND summary=%s LIMIT 1",
                (report_date, customer, summary),
            ).fetchone()
            if existing:
                skipped += 1
                continue
            con.execute(
                "INSERT INTO complaints(report_date,customer,summary,follow_up,complaint_type,priority,status,"
                "status_changed_at,resolution,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    report_date,
                    customer,
                    summary,
                    follow_up,
                    complaint_type,
                    priority,
                    status,
                    status_changed_at,
                    resolution,
                    updated_at,
                ),
            )
            imported += 1
    return {"imported": imported, "skipped": skipped}


@app.get("/api/latest-actual-date")
def latest_actual_date(request: Request):
    require_home_access(request)
    with db() as con:
        row = con.execute(
            "SELECT MAX(report_date) AS report_date FROM sales WHERE actual <> 0"
        ).fetchone()
    return row["report_date"].isoformat() if row["report_date"] else None


@app.get("/api/monthly")
def monthly_summary(
    request: Request,
    year: int,
    through_date: Optional[str] = None,
):
    require_login(request)

    if year < 2000 or year > 2100:
        raise HTTPException(
            status_code=400,
            detail="Tahun harus berada di antara 2000 dan 2100."
        )

    end_date = None
    if through_date:
        try:
            end_date = date.fromisoformat(through_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Tanggal batas harus berformat YYYY-MM-DD.",
            ) from exc
        if end_date.year != year:
            raise HTTPException(
                status_code=400,
                detail="Tanggal batas harus berada pada tahun yang dipilih.",
            )

    with db() as con:
        query = """
            SELECT
                c.customer_key,
                c.customer_name,
                c.operator,
                MONTH(s.report_date) AS month_number,
                SUM(s.so) AS total_so,
                SUM(s.actual) AS total_actual
            FROM sales s
            JOIN customers c
                ON c.customer_key = s.customer_key
            WHERE YEAR(s.report_date) = %s
        """
        parameters = [year]
        if end_date:
            query += " AND s.report_date <= %s"
            parameters.append(end_date.isoformat())
        query += """
            GROUP BY
                c.customer_key,
                c.customer_name,
                c.operator,
                MONTH(s.report_date)
            ORDER BY
                c.operator,
                c.customer_name,
                month_number
        """
        rows = con.execute(query, tuple(parameters)).fetchall()

    items = [
        {
            "customer_key": row["customer_key"],
            "customer": row["customer_name"],
            "operator": row["operator"],
            "month": int(row["month_number"]),
            "so": float(row["total_so"] or 0),
            "actual": float(row["total_actual"] or 0),
        }
        for row in rows
    ]

    return {
        "year": year,
        "through_date": end_date.isoformat() if end_date else None,
        "items": items,
    }


@app.get("/api/monthly-range")
def monthly_range_summary(request: Request, start_date: str, end_date: str):
    require_login(request)
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Tanggal harus berformat YYYY-MM-DD.") from exc
    if start > end:
        raise HTTPException(status_code=400, detail="Tanggal awal tidak boleh melewati tanggal akhir.")

    with db() as con:
        sales_rows = con.execute(
            """
            SELECT
                s.report_date,
                c.customer_key,
                c.customer_name,
                c.operator,
                s.so,
                s.actual,
                s.id,
                c.customer_key LIKE 'manualfob-%%' AS manual_fob
            FROM sales s
            JOIN customers c ON c.customer_key = s.customer_key
            WHERE s.report_date BETWEEN %s AND %s
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        customer_rows = con.execute(
            "SELECT customer_key, customer_name, operator FROM customers"
        ).fetchall()

    rows, sales_order_unmapped = overlay_sales_order_forecast(
        sales_rows,
        customer_rows,
        get_sales_order_data(),
        start,
        end,
    )
    grouped_rows = {}
    for row in rows:
        period = row["report_date"][:7]
        key = (row["customer_key"], row["customer_name"], row["operator"], period)
        grouped = grouped_rows.setdefault(key, {
            "customer_key": row["customer_key"],
            "customer": row["customer_name"],
            "operator": row["operator"],
            "period": period,
            "so": 0.0,
            "actual": 0.0,
            "actual_is_forecast": False,
        })
        grouped["so"] += row["so"]
        grouped["actual"] += row["actual"]
        grouped["actual_is_forecast"] = (
            grouped["actual_is_forecast"] or row["actual_is_forecast"]
        )
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "items": sorted(
            grouped_rows.values(),
            key=lambda row: (row["period"], row["operator"], row["customer"]),
        ),
        "sales_order_unmapped": sales_order_unmapped,
    }


def build_monthly_export(year, month, sales_rows, monthly_target):
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    day_count = (month_end - month_start).days + 1

    month_names = (
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    )
    month_label = f"{month_names[month - 1]} {year}"
    operator_names = (*OPERATORS, "OFF")
    sales_by_day = {}
    operator_totals = {
        operator: {"so": 0.0, "actual": 0.0}
        for operator in operator_names
    }
    for row in sales_rows:
        report_day = row["report_date"]
        if isinstance(report_day, str):
            report_day = date.fromisoformat(report_day)
        operator = row["operator"]
        sale = {
            "customer": row["customer_name"],
            "so": float(row["so"] or 0),
            "actual": float(row["actual"] or 0),
            "operator": operator,
        }
        sales_by_day.setdefault(report_day, []).append(sale)
        operator_total = operator_totals.setdefault(
            operator, {"so": 0.0, "actual": 0.0}
        )
        operator_total["so"] += sale["so"]
        operator_total["actual"] += sale["actual"]

    days = [
        month_start + timedelta(days=offset)
        for offset in range(day_count)
    ]
    daily_totals = {}
    week_groups = {}
    total_so = 0.0
    total_actual = 0.0
    for report_day in days:
        rows = sales_by_day.get(report_day, [])
        day_so = sum(row["so"] for row in rows)
        day_actual = sum(row["actual"] for row in rows)
        daily_totals[report_day] = (day_so, day_actual, rows)
        total_so += day_so
        total_actual += day_actual

        week_start = report_day - timedelta(days=report_day.weekday())
        week = week_groups.setdefault(
            week_start,
            {"days": [], "so": 0.0, "actual": 0.0},
        )
        week["days"].append(report_day)
        week["so"] += day_so
        week["actual"] += day_actual

    target = float(monthly_target) if monthly_target is not None else total_so
    daily_target = target / day_count if day_count else 0.0

    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "SUMMARY REPORT"
    header_fill = PatternFill("solid", fgColor="176341")
    subheader_fill = PatternFill("solid", fgColor="E4F4E9")
    total_fill = PatternFill("solid", fgColor="DFF3E6")
    white_bold = Font(name="Aptos", color="FFFFFF", bold=True)
    title_font = Font(name="Aptos Display", size=16, bold=True, color="174632")
    bold_font = Font(name="Aptos", bold=True, color="174632")
    thin_green = Side(style="thin", color="D5E5DA")
    number_format = '#,##0.00;[Red]-#,##0.00;0.00'
    percent_format = '0.00%;[Red]-0.00%;0.00%'

    def setup_sheet(sheet, title, last_column, header_rows):
        sheet.sheet_view.showGridLines = False
        sheet.merge_cells(
            start_row=1,
            start_column=1,
            end_row=1,
            end_column=last_column,
        )
        title_cell = sheet.cell(1, 1, title)
        title_cell.font = title_font
        title_cell.alignment = Alignment(vertical="center")
        sheet.row_dimensions[1].height = 26
        for header_row in header_rows:
            for cell in sheet[header_row]:
                if cell.column <= last_column:
                    cell.fill = header_fill
                    cell.font = white_bold
                    cell.alignment = Alignment(
                        horizontal="center",
                        vertical="center",
                        wrap_text=True,
                    )
                    cell.border = Border(bottom=thin_green)
            sheet.row_dimensions[header_row].height = 30
        sheet.freeze_panes = f"A{max(header_rows) + 1}"

    def style_data_region(sheet, min_row, max_row, max_column, total_rows=()):
        for row_index in range(min_row, max_row + 1):
            is_total = row_index in total_rows
            for column_index in range(1, max_column + 1):
                cell = sheet.cell(row_index, column_index)
                cell.border = Border(bottom=thin_green)
                if is_total:
                    cell.fill = total_fill
                    cell.font = bold_font
                elif row_index % 2 == 0:
                    cell.fill = PatternFill("solid", fgColor="F7FBF8")
                if column_index > 1 and isinstance(cell.value, (int, float)):
                    cell.number_format = number_format

    summary_sheet.merge_cells("A2:B2")
    summary_sheet["A2"] = f"Periode: {month_label}"
    summary_sheet["A2"].font = bold_font
    summary_sheet.append([])
    summary_sheet.append(["Ringkasan", "Nilai"])
    summary_rows = [
        ("Total Target", target),
        ("Total SO Transaksi", total_so),
        ("Total Actual", total_actual),
        ("Diff (Actual - Target)", total_actual - target),
        ("Pencapaian Target", total_actual / target if target else 0),
    ]
    for item in summary_rows:
        summary_sheet.append(item)
    summary_sheet["A4"].fill = header_fill
    summary_sheet["B4"].fill = header_fill
    summary_sheet["A4"].font = white_bold
    summary_sheet["B4"].font = white_bold
    summary_sheet["B9"].number_format = percent_format
    summary_sheet.append([])
    operator_header_row = 11
    summary_sheet.append(["Operator", "SO", "Actual", "Diff (Actual - SO)", "Pencapaian"])
    for operator in operator_names:
        totals = operator_totals[operator]
        summary_sheet.append([
            operator,
            totals["so"],
            totals["actual"],
            totals["actual"] - totals["so"],
            totals["actual"] / totals["so"] if totals["so"] else 0,
        ])
    summary_total_row = summary_sheet.max_row + 1
    summary_sheet.append([
        "TOTAL",
        total_so,
        total_actual,
        total_actual - total_so,
        total_actual / total_so if total_so else 0,
    ])
    setup_sheet(summary_sheet, f"SUMMARY REPORT - {month_label}", 5, [4, operator_header_row])
    style_data_region(summary_sheet, 5, 9, 2)
    style_data_region(summary_sheet, operator_header_row + 1, summary_total_row, 5, [summary_total_row])
    for row_index in range(5, 9):
        summary_sheet.cell(row_index, 2).number_format = number_format
    summary_sheet["B9"].number_format = percent_format
    for row_index in range(operator_header_row + 1, summary_total_row + 1):
        summary_sheet.cell(row_index, 5).number_format = percent_format
    summary_sheet.column_dimensions["A"].width = 28
    for column in ("B", "C", "D", "E"):
        summary_sheet.column_dimensions[column].width = 22

    weekly_sheet = workbook.create_sheet("Weekly Summary")
    weekly_headers = [
        "Minggu", "Periode Tanggal", "Target Rencana", "Total SO",
        "Actual", "Diff Actual - SO", "Diff Actual - Target", "Actual/Target",
    ]
    weekly_sheet.append([f"WEEKLY SUMMARY - {month_label}"])
    weekly_sheet.append([
        "Target mingguan dijumlahkan dari target harian (target bulanan dibagi rata menurut hari kalender). "
        "Jika target bulanan belum diinput, total SO transaksi digunakan sebagai target."
    ])
    weekly_sheet.merge_cells("A2:H2")
    weekly_sheet["A2"].font = Font(name="Aptos", size=9, italic=True, color="527160")
    weekly_sheet["A2"].alignment = Alignment(wrap_text=True, vertical="center")
    weekly_sheet.row_dimensions[2].height = 28
    weekly_sheet.append(weekly_headers)
    for week_number, (week_start, week) in enumerate(week_groups.items(), start=1):
        week_target = daily_target * len(week["days"])
        week_diff_target = week["actual"] - week_target
        weekly_sheet.append([
            f"Week {week_number}",
            f'{week["days"][0].strftime("%d %b")} - {week["days"][-1].strftime("%d %b")}',
            week_target,
            week["so"],
            week["actual"],
            week["actual"] - week["so"],
            week_diff_target,
            week["actual"] / week_target if week_target else 0,
        ])
    weekly_total_row = weekly_sheet.max_row + 1
    weekly_sheet.append([
        "TOTAL",
        month_label,
        target,
        total_so,
        total_actual,
        total_actual - total_so,
        total_actual - target,
        total_actual / target if target else 0,
    ])
    setup_sheet(weekly_sheet, f"WEEKLY SUMMARY - {month_label}", len(weekly_headers), [3])
    style_data_region(weekly_sheet, 4, weekly_total_row, len(weekly_headers), [weekly_total_row])
    for row_index in range(4, weekly_total_row + 1):
        weekly_sheet.cell(row_index, 8).number_format = percent_format
    for column, width in enumerate((16, 24, 20, 20, 20, 22, 24, 18), start=1):
        weekly_sheet.column_dimensions[get_column_letter(column)].width = width

    daily_sheet = workbook.create_sheet("Daily Summary")
    daily_headers = [
        "Tanggal", "Hari", "Target Rencana", "Total SO", "Actual",
        "Diff Actual - SO", "Diff Actual - Target",
    ]
    daily_sheet.append([f"DAILY SUMMARY - {month_label}"])
    daily_sheet.append([
        "Target harian dihitung dari target bulanan dibagi rata menurut hari kalender. "
        "Jika target bulanan belum diinput, total SO transaksi digunakan sebagai target."
    ])
    daily_sheet.merge_cells("A2:G2")
    daily_sheet["A2"].font = Font(name="Aptos", size=9, italic=True, color="527160")
    daily_sheet["A2"].alignment = Alignment(wrap_text=True, vertical="center")
    daily_sheet.row_dimensions[2].height = 28
    daily_sheet.append(daily_headers)
    day_names = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
    for report_day in days:
        day_so, day_actual, _ = daily_totals[report_day]
        daily_sheet.append([
            report_day,
            day_names[report_day.weekday()],
            daily_target,
            day_so,
            day_actual,
            day_actual - day_so,
            day_actual - daily_target,
        ])
        daily_sheet.cell(daily_sheet.max_row, 1).number_format = "dd mmmm yyyy"
    daily_total_row = daily_sheet.max_row + 1
    daily_sheet.append([
        "TOTAL",
        "",
        target,
        total_so,
        total_actual,
        total_actual - total_so,
        total_actual - target,
    ])
    setup_sheet(daily_sheet, f"DAILY SUMMARY - {month_label}", len(daily_headers), [3])
    style_data_region(daily_sheet, 4, daily_total_row, len(daily_headers), [daily_total_row])
    daily_sheet.column_dimensions["A"].width = 20
    daily_sheet.column_dimensions["B"].width = 16
    for column in range(3, len(daily_headers) + 1):
        daily_sheet.column_dimensions[get_column_letter(column)].width = 22

    for operator in OPERATORS:
        sheet = workbook.create_sheet(operator)
        headers = [
            "Tanggal", "Hari", "Minggu", "Customer", "SO", "Actual",
            "Diff Actual - SO",
        ]
        sheet.append([f"SALES ORDER - {operator} - {month_label}"])
        sheet.append([])
        sheet.append(headers)
        total_row_indices = []
        operator_total = {"so": 0.0, "actual": 0.0}
        for report_day in days:
            day_rows = sorted(
                (
                    row for row in sales_by_day.get(report_day, [])
                    if row["operator"] == operator
                ),
                key=lambda row: row["customer"].casefold(),
            )
            week_start = report_day - timedelta(days=report_day.weekday())
            week_number = list(week_groups).index(week_start) + 1
            for row in day_rows:
                sheet.append([
                    report_day,
                    day_names[report_day.weekday()],
                    f"Week {week_number}",
                    row["customer"],
                    row["so"],
                    row["actual"],
                    row["actual"] - row["so"],
                ])
                sheet.cell(sheet.max_row, 1).number_format = "dd mmmm yyyy"
                operator_total["so"] += row["so"]
                operator_total["actual"] += row["actual"]
            day_so = sum(row["so"] for row in day_rows)
            day_actual = sum(row["actual"] for row in day_rows)
            sheet.append([
                report_day,
                day_names[report_day.weekday()],
                f"Week {week_number}",
                "TOTAL HARIAN",
                day_so,
                day_actual,
                day_actual - day_so,
            ])
            sheet.cell(sheet.max_row, 1).number_format = "dd mmmm yyyy"
            total_row_indices.append(sheet.max_row)

        operator_grand_total_row = sheet.max_row + 1
        sheet.append([
            "",
            "",
            "",
            "TOTAL BULAN",
            operator_total["so"],
            operator_total["actual"],
            operator_total["actual"] - operator_total["so"],
        ])
        total_row_indices.append(operator_grand_total_row)
        setup_sheet(sheet, f"SALES ORDER - {operator} - {month_label}", len(headers), [3])
        style_data_region(sheet, 4, operator_grand_total_row, len(headers), total_row_indices)
        for column, width in enumerate((20, 15, 14, 36, 20, 20, 24), start=1):
            sheet.column_dimensions[get_column_letter(column)].width = width
        sheet.auto_filter.ref = f"A3:G{max(3, operator_grand_total_row - 1)}"

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


@app.get("/api/monthly/export")
def export_monthly_report(request: Request, year: int, month: int):
    require_login(request)
    if year < 2000 or year > 2100 or month < 1 or month > 12:
        raise HTTPException(
            status_code=400,
            detail="Tahun atau bulan laporan tidak valid.",
        )

    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    with db() as con:
        sales_rows = con.execute(
            """
            SELECT s.report_date, c.customer_name, c.operator, s.so, s.actual
            FROM sales s
            JOIN customers c ON c.customer_key=s.customer_key
            WHERE s.report_date BETWEEN %s AND %s
            ORDER BY s.report_date, c.operator, c.customer_name
            """,
            (month_start.isoformat(), month_end.isoformat()),
        ).fetchall()
        target_row = con.execute(
            "SELECT so FROM monthly_so_targets WHERE month_start=%s",
            (month_start.isoformat(),),
        ).fetchone()

    workbook = build_monthly_template_export(
        year,
        month,
        sales_rows,
        float(target_row["so"]) if target_row is not None else None,
    )
    month_names = (
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember",
    )
    filename = f'Rekap_Bulanan_{month_names[month - 1]}_{year}.xlsx'
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/dashboard")
def dashboard(
    request: Request,
    report_date: Optional[str] = None,
    trend_period: str = "daily",
):
    require_login(request)
    with db() as con:
        if not report_date:
            row = con.execute("SELECT MAX(report_date) AS d FROM sales").fetchone()
            report_date = row["d"]
        if not report_date:
            return {
                "report_date": None,
                "total_so": 0,
                "total_actual": 0,
                "diff": 0,
                "customer_active": 0,
                "operators": {},
                "operator_totals": {},
                "trend_period": trend_period,
                "trend": [],
                "latest_import": None,
            }
        if isinstance(report_date, date):
            report_date = report_date.isoformat()
        try:
            selected_date = date.fromisoformat(report_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Format tanggal tidak valid.")
        trend_period = trend_period.strip().lower()
        if trend_period not in {"daily", "weekly", "monthly", "yearly"}:
            raise HTTPException(status_code=400, detail="Periode tren tidak valid.")

        rows = con.execute("""
            SELECT c.customer_name, c.operator, c.customer_key,
                   s.so, s.actual, s.id,
                   c.customer_key LIKE 'manualfob-%%' AS manual_fob
            FROM sales s JOIN customers c ON c.customer_key=s.customer_key
            WHERE s.report_date=%s ORDER BY c.operator, c.customer_name
        """, (report_date,)).fetchall()
        customer_rows = con.execute(
            "SELECT customer_key, customer_name, operator FROM customers"
        ).fetchall()
        rows, sales_order_unmapped = overlay_sales_order_forecast(
            [dict(row, report_date=report_date) for row in rows],
            customer_rows,
            get_sales_order_data(),
            selected_date,
            selected_date,
        )
        operator_data = {op: [] for op in (*OPERATORS, "OFF")}
        operator_totals = {
            op: {"so": 0.0, "actual": 0.0, "diff": 0.0, "customers": 0}
            for op in (*OPERATORS, "OFF")
        }
        for r in rows:
            customer_row = {
                "customer": r["customer_name"],
                "customer_key": r["customer_key"],
                "so": r["so"],
                "actual": r["actual"],
                "actual_is_forecast": r["actual_is_forecast"],
                "manual_fob": bool(r.get("manual_fob", False)),
                "diff": r["diff"],
            }
            if customer_row["manual_fob"] and r.get("id") is not None:
                customer_row["manual_fob_id"] = r["id"]
            operator_data[r["operator"]].append(customer_row)

            totals = operator_totals[r["operator"]]
            so_value = float(r["so"] or 0)
            actual_value = float(r["actual"] or 0)
            totals["so"] += so_value
            totals["actual"] += actual_value
            totals["diff"] += actual_value - so_value
            if so_value != 0 or actual_value != 0:
                totals["customers"] += 1

        if trend_period == "daily":
            trend_start = selected_date - timedelta(days=29)
            group_expression = "s.report_date"
        elif trend_period == "weekly":
            selected_week_start = selected_date - timedelta(days=selected_date.weekday())
            trend_start = selected_week_start - timedelta(weeks=11)
            group_expression = "DATE_SUB(s.report_date, INTERVAL WEEKDAY(s.report_date) DAY)"
        elif trend_period == "monthly":
            month_index = selected_date.year * 12 + selected_date.month - 1 - 11
            trend_start = date(month_index // 12, month_index % 12 + 1, 1)
            group_expression = "DATE_FORMAT(s.report_date, '%%Y-%%m-01')"
        else:
            trend_start = date(selected_date.year - 4, 1, 1)
            group_expression = "MAKEDATE(YEAR(s.report_date), 1)"

        trend_rows = con.execute(
            f"""
            SELECT {group_expression} AS period_start,
                   SUM(s.so) AS so,
                   SUM(s.actual) AS actual
            FROM sales s JOIN customers c ON c.customer_key=s.customer_key
            WHERE s.report_date BETWEEN %s AND %s
            GROUP BY period_start ORDER BY period_start
            """,
            (trend_start.isoformat(), report_date),
        ).fetchall()
        trend_values = {}
        for row in trend_rows:
            period_start = row["period_start"]
            if isinstance(period_start, date):
                period_start = period_start.isoformat()
            trend_values[str(period_start)] = {
                "so": float(row["so"] or 0),
                "actual": float(row["actual"] or 0),
            }

        trend_periods = []
        if trend_period == "daily":
            current = trend_start
            while current <= selected_date:
                trend_periods.append(current.isoformat())
                current += timedelta(days=1)
        elif trend_period == "weekly":
            current = trend_start
            last_period = selected_date - timedelta(days=selected_date.weekday())
            while current <= last_period:
                trend_periods.append(current.isoformat())
                current += timedelta(weeks=1)
        elif trend_period == "monthly":
            current = trend_start
            while current <= selected_date:
                trend_periods.append(current.isoformat())
                month_index = current.year * 12 + current.month
                current = date(month_index // 12, month_index % 12 + 1, 1)
        else:
            trend_periods = [
                date(year, 1, 1).isoformat()
                for year in range(trend_start.year, selected_date.year + 1)
            ]

        latest = con.execute("SELECT filename, imported_at FROM import_history WHERE status='BERHASIL' ORDER BY id DESC LIMIT 1").fetchone()
        total_so = sum(float(r["so"] or 0) for r in rows)
        total_actual = sum(float(r["actual"] or 0) for r in rows)
        return {
            "report_date": report_date,
            "total_so": total_so,
            "total_actual": total_actual,
            "diff": total_actual - total_so,
            "customer_active": sum(
                r["operator"] != "OFF"
                and ((r["so"] or 0) != 0 or (r["actual"] or 0) != 0)
                for r in rows
            ),
            "operators": operator_data,
            "operator_totals": operator_totals,
            "sales_order_unmapped": sales_order_unmapped,
            "trend_period": trend_period,
            "trend": [
                {
                    "period_start": period_start,
                    "has_data": period_start in trend_values,
                    **trend_values.get(period_start, {"so": 0.0, "actual": 0.0}),
                }
                for period_start in trend_periods
            ],
            "latest_import": dict(latest) if latest else None,
            "period": selected_date.strftime("%B %Y")
        }


@app.get("/api/weekly-volume")
def weekly_volume(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    operator: Optional[str] = None,
):
    require_login(request)
    with db() as con:
        if not start_date or not end_date:
            latest = con.execute("SELECT MAX(report_date) AS latest_date FROM sales").fetchone()["latest_date"]
            if not latest:
                return {"start_date": None, "end_date": None, "operator": "ALL", "weeks": [], "totals": {"so": 0, "target": 0, "actual": 0, "diff": 0, "achievement": 0}}
            latest = latest if isinstance(latest, date) else date.fromisoformat(str(latest))
            start = latest - timedelta(days=latest.weekday())
            end = start + timedelta(days=6)
        else:
            try:
                start = date.fromisoformat(start_date)
                end = date.fromisoformat(end_date)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Format tanggal harus YYYY-MM-DD.") from exc

        if start > end:
            raise HTTPException(status_code=400, detail="Tanggal mulai tidak boleh melewati tanggal akhir.")
        selected_operator = (operator or "ALL").strip().upper()
        if selected_operator not in {"ALL", *OPERATORS}:
            raise HTTPException(status_code=400, detail="Operator tidak dikenal.")

        params = [start.isoformat(), end.isoformat()]
        operator_filter = ""
        if selected_operator != "ALL":
            operator_filter = " AND c.operator=%s"
            params.append(selected_operator)
        rows = con.execute(
            "SELECT s.report_date,c.operator,SUM(s.so) AS so,SUM(s.actual) AS actual "
            "FROM sales s JOIN customers c ON c.customer_key=s.customer_key "
            "WHERE s.report_date BETWEEN %s AND %s" + operator_filter + " "
            "GROUP BY s.report_date,c.operator ORDER BY s.report_date,c.operator",
            tuple(params),
        ).fetchall()
        target_rows = con.execute(
            "SELECT so FROM monthly_so_targets WHERE month_start BETWEEN %s AND %s",
            (
                start.replace(day=1).isoformat(),
                end.replace(day=1).isoformat(),
            ),
        ).fetchall()
    weeks_by_start = {}
    week_start = start - timedelta(days=start.weekday())
    last_week_start = end - timedelta(days=end.weekday())
    while week_start <= last_week_start:
        iso_week = week_start.isocalendar()
        weeks_by_start[week_start] = {
            "week": iso_week.week,
            "label": f"Week {iso_week.week}",
            "start_date": week_start.isoformat(),
            "end_date": (week_start + timedelta(days=6)).isoformat(),
            "operators": {name: {"so": 0, "actual": 0} for name in (*OPERATORS, "OFF")},
        }
        week_start += timedelta(days=7)

    detail_weeks_by_month_start = {}
    month_start = start.replace(day=1)
    last_month_start = end.replace(day=1)
    while month_start <= last_month_start:
        if month_start.month == 12:
            month_end = date(month_start.year + 1, 1, 1) - timedelta(days=1)
            next_month = date(month_start.year + 1, 1, 1)
        else:
            next_month = date(month_start.year, month_start.month + 1, 1)
            month_end = next_month - timedelta(days=1)
        week_start = month_start - timedelta(days=month_start.weekday())
        while week_start <= month_end:
            period_start = max(week_start, month_start)
            period_end = min(week_start + timedelta(days=6), month_end)
            if period_end >= start and period_start <= end:
                week_number = week_start.isocalendar().week
                detail_weeks_by_month_start[(month_start, week_start)] = {
                    "week": week_number,
                    "label": f"Week {week_number}",
                    "start_date": period_start.isoformat(),
                    "end_date": period_end.isoformat(),
                    "so": 0.0,
                    "actual": 0.0,
                }
            week_start += timedelta(days=7)
        month_start = next_month

    for row in rows:
        report_date = row["report_date"]
        if isinstance(report_date, str):
            report_date = date.fromisoformat(report_date)
        week_start = report_date - timedelta(days=report_date.weekday())
        week = weeks_by_start[week_start]
        operator_total = week["operators"][row["operator"]]
        operator_total["so"] += float(row["so"] or 0)
        operator_total["actual"] += float(row["actual"] or 0)
        month_start = report_date.replace(day=1)
        detail_week = detail_weeks_by_month_start[
            (month_start, week_start)
        ]
        detail_week["so"] += float(row["so"] or 0)
        detail_week["actual"] += float(row["actual"] or 0)

    weeks = []
    total_so = total_actual = 0
    for week in weeks_by_start.values():
        week_so = sum(item["so"] for item in week["operators"].values())
        week_actual = sum(item["actual"] for item in week["operators"].values())
        week["so"] = week_so
        week["actual"] = week_actual
        week["diff"] = week_actual - week_so
        week["achievement"] = week_actual / week_so * 100 if week_so else 0
        total_so += week_so
        total_actual += week_actual
        weeks.append(week)

    detail_weeks = []
    for week in detail_weeks_by_month_start.values():
        week["diff"] = week["actual"] - week["so"]
        week["achievement"] = week["actual"] / week["so"] * 100 if week["so"] else 0
        detail_weeks.append(week)

    total_target = (
        sum(float(row["so"] or 0) for row in target_rows)
        if target_rows else total_so
    )
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "operator": selected_operator,
        "weeks": weeks,
        "detail_weeks": detail_weeks,
        "totals": {
            "so": total_so,
            "target": total_target,
            "actual": total_actual,
            "diff": total_actual - total_so,
            "achievement": total_actual / total_so * 100 if total_so else 0,
        },
    }


@app.get("/api/weekly-average-price")
def weekly_average_price(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    region: Optional[str] = None,
    operator: Optional[str] = None,
):
    require_login(request)
    with db() as con:
        if not start_date or not end_date:
            latest = con.execute("SELECT MAX(report_date) AS latest_date FROM sales").fetchone()["latest_date"]
            if not latest:
                return {"start_date": None, "end_date": None, "regions": [], "rows": [], "weeks": [], "totals": {"so_price_rp_sm3": 0, "actual_price_rp_sm3": 0, "diff": 0, "achievement": 0}}
            latest = latest if isinstance(latest, date) else date.fromisoformat(str(latest))
            start = latest - timedelta(days=latest.weekday())
            end = start + timedelta(days=6)
        else:
            try:
                start = date.fromisoformat(start_date)
                end = date.fromisoformat(end_date)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Format tanggal harus YYYY-MM-DD.") from exc
        if start > end:
            raise HTTPException(status_code=400, detail="Tanggal mulai tidak boleh melewati tanggal akhir.")
        selected_operator = (operator or "ALL").strip().upper()
        if selected_operator not in {"ALL", *OPERATORS}:
            raise HTTPException(status_code=400, detail="Operator tidak dikenal.")

        clauses = ["weekly_sales.week_start BETWEEN %s AND %s"]
        params = [
            start.isoformat(),
            end.isoformat(),
            (start - timedelta(days=start.weekday())).isoformat(),
            (end - timedelta(days=end.weekday())).isoformat(),
        ]
        if selected_operator != "ALL":
            clauses.append("c.operator=%s")
            params.append(selected_operator)
        if region and region != "ALL":
            clauses.append("COALESCE(price_inputs.region,'')=%s")
            params.append(region)

        query = """
            SELECT weekly_sales.week_start,c.customer_key,c.customer_name,c.operator,
                   weekly_sales.so,weekly_sales.actual,
                   COALESCE(price_inputs.region,'') AS region,
                   COALESCE(price_inputs.volume_mmbtu,0) AS volume_mmbtu,
                   COALESCE(price_inputs.price_usd_per_sm3,0) AS price_usd_per_sm3,
                   COALESCE(price_inputs.exchange_rate,0) AS exchange_rate
            FROM (
                SELECT DATE_SUB(report_date, INTERVAL WEEKDAY(report_date) DAY) AS week_start,
                       customer_key,SUM(so) AS so,SUM(actual) AS actual
                FROM sales
                WHERE report_date BETWEEN %s AND %s
                GROUP BY week_start,customer_key
            ) AS weekly_sales
            JOIN customers c ON c.customer_key=weekly_sales.customer_key
            LEFT JOIN weekly_average_price_inputs price_inputs
              ON price_inputs.week_start=weekly_sales.week_start
             AND price_inputs.customer_key=weekly_sales.customer_key
        """
        query += " WHERE " + " AND ".join(clauses) + " ORDER BY weekly_sales.week_start,price_inputs.region,c.customer_name"
        rows = con.execute(query, tuple(params)).fetchall()

    results = []
    region_totals = {}
    week_totals = {}
    weighted_so_price = weighted_actual_price = so_volume = actual_volume = 0.0
    for row in rows:
        item = {
            "week_start": row["week_start"].isoformat(),
            "customer_key": row["customer_key"],
            "customer": row["customer_name"],
            "operator": row["operator"],
            "region": row["region"] or "Belum ditentukan",
            "so_sm3": float(row["so"] or 0),
            "actual_sm3": float(row["actual"] or 0),
            "volume_mmbtu": float(row["volume_mmbtu"] or 0),
            "price_usd_per_sm3": float(row["price_usd_per_sm3"] or 0),
            "exchange_rate": float(row["exchange_rate"] or 0),
        }
        item["total_usd"] = item["actual_sm3"] * item["price_usd_per_sm3"]
        item["rupiah"] = item["total_usd"] * item["exchange_rate"]
        so_price = item["price_usd_per_sm3"] * item["exchange_rate"]
        actual_price = so_price
        if item["price_usd_per_sm3"] > 0 and item["exchange_rate"] > 0:
            weighted_so_price += item["so_sm3"] * so_price
            weighted_actual_price += item["actual_sm3"] * actual_price
            so_volume += item["so_sm3"]
            actual_volume += item["actual_sm3"]

        region_total = region_totals.setdefault(item["region"], {"so": 0.0, "actual": 0.0, "weighted_so": 0.0, "weighted_actual": 0.0})
        region_total["so"] += item["so_sm3"]
        region_total["actual"] += item["actual_sm3"]
        region_total["weighted_so"] += item["so_sm3"] * so_price
        region_total["weighted_actual"] += item["actual_sm3"] * actual_price

        week_total = week_totals.setdefault(item["week_start"], {"so_volume": 0.0, "actual_volume": 0.0, "so_weighted": 0.0, "actual_weighted": 0.0})
        week_total["so_volume"] += item["so_sm3"]
        week_total["actual_volume"] += item["actual_sm3"]
        week_total["so_weighted"] += item["so_sm3"] * so_price
        week_total["actual_weighted"] += item["actual_sm3"] * actual_price
        results.append(item)

    regions = [{
        "region": name,
        "so_price_rp_sm3": values["weighted_so"] / values["so"] if values["so"] else 0,
        "actual_price_rp_sm3": values["weighted_actual"] / values["actual"] if values["actual"] else 0,
        "diff": (values["weighted_actual"] / values["actual"] if values["actual"] else 0) - (values["weighted_so"] / values["so"] if values["so"] else 0),
        "achievement": (values["weighted_actual"] / values["actual"] / (values["weighted_so"] / values["so"]) * 100) if values["so"] and values["actual"] and values["weighted_so"] else 0,
    } for name, values in sorted(region_totals.items())]
    weeks = []
    for week_start, values in sorted(week_totals.items()):
        iso = date.fromisoformat(week_start).isocalendar()
        weeks.append({
            "week_start": week_start,
            "week": iso.week,
            "so_price_rp_sm3": values["so_weighted"] / values["so_volume"] if values["so_volume"] else 0,
            "actual_price_rp_sm3": values["actual_weighted"] / values["actual_volume"] if values["actual_volume"] else 0,
        })
    so_average = weighted_so_price / so_volume if so_volume else 0
    actual_average = weighted_actual_price / actual_volume if actual_volume else 0
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "regions": regions,
        "rows": results,
        "weeks": weeks,
        "totals": {
            "so_price_rp_sm3": so_average,
            "actual_price_rp_sm3": actual_average,
            "diff": actual_average - so_average,
            "achievement": actual_average / so_average * 100 if so_average else 0,
        },
    }


def calculate_average_price(
    sm3,
    factor,
    price_unit,
    price_usd,
    price_rp,
    exchange_rate,
    mmbtu_override=None,
    total_usd_override=None,
    rupiah_override=None,
    rupiah_multiplier=None,
):
    volume_mmbtu = (
        float(mmbtu_override)
        if mmbtu_override is not None
        else sm3 / factor if factor > 0 else 0.0
    )
    if price_unit == "IDR_SM3":
        rupiah = sm3 * price_rp
        total_usd = rupiah / exchange_rate if exchange_rate > 0 else 0.0
    else:
        total_usd = volume_mmbtu * price_usd
        rate = float(rupiah_multiplier or 0)
        rupiah = total_usd * (rate if rate > 0 else exchange_rate)
    if total_usd_override is not None:
        total_usd = float(total_usd_override)
        if rupiah_override is None:
            rupiah = total_usd * exchange_rate
    if rupiah_override is not None:
        rupiah = float(rupiah_override)
    return volume_mmbtu, total_usd, rupiah


def has_valid_average_price(
    price_unit,
    price_usd,
    price_rp,
    factor,
    exchange_rate,
    mmbtu_override=None,
    total_usd_override=None,
    rupiah_override=None,
    rupiah_multiplier=None,
):
    if price_unit == "IDR_SM3":
        return price_rp > 0
    has_workbook_totals = all(
        value is not None
        for value in (mmbtu_override, total_usd_override, rupiah_override)
    )
    return price_usd > 0 and (
        (factor > 0 and (exchange_rate > 0 or float(rupiah_multiplier or 0) > 0))
        or has_workbook_totals
    )


AVERAGE_PRICE_WORKBOOK_MONTH_NAMES = {
    month: names for month, names in AVERAGE_PRICE_MONTH_HEADERS.items()
}


def parse_monthly_average_price_workbook(content: bytes, filename: str):
    try:
        workbook = load_workbook(BytesIO(content), data_only=True, read_only=True)
    except (BadZipFile, InvalidFileException, OSError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=400,
            detail="File Excel Average Price tidak dapat dibaca.",
        ) from exc

    months = []
    try:
        for worksheet in workbook.worksheets:
            title = str(worksheet.title).strip()
            if not norm(title).startswith("avg"):
                continue
            month_name = norm(title)[3:]
            month_number = next(
                (
                    month
                    for month, names in AVERAGE_PRICE_WORKBOOK_MONTH_NAMES.items()
                    if month_name in {norm(name) for name in names}
                ),
                None,
            )
            if month_number is None:
                continue
            if worksheet.max_row > 10000 or worksheet.max_column > 100:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ukuran sheet {title} melebihi batas yang didukung.",
                )

            title_value = worksheet.cell(1, 1).value
            if isinstance(title_value, datetime):
                year = title_value.year
            else:
                year_match = re.search(r"\b(20\d{2})\b", str(title_value or ""))
                if not year_match:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Tahun laporan tidak ditemukan pada sheet {title}.",
                    )
                year = int(year_match.group(1))

            is_three_region_layout = month_number >= 8
            blocks = (
                [("JAWA BARAT", 2), ("JAWA TENGAH", 10), ("JAWA TIMUR", 16)]
                if is_three_region_layout
                else [("JAWA BARAT", 2), ("JAWA TENGAH DAN TIMUR", 10)]
            )
            exchange_rate = None
            for _, customer_column in blocks:
                for row_number in range(4, worksheet.max_row + 1):
                    label = worksheet.cell(row_number, customer_column).value
                    if not isinstance(label, str) or "kursjisdor" not in norm(label):
                        continue
                    rate = worksheet.cell(row_number, customer_column + 1).value
                    if isinstance(rate, (int, float)) and math.isfinite(float(rate)) and rate > 0:
                        exchange_rate = float(rate)
                        break
                if exchange_rate is not None:
                    break

            detail_entries = []
            for block_region, customer_column in blocks:
                for row_number in range(4, worksheet.max_row + 1):
                    customer = worksheet.cell(row_number, customer_column).value
                    if not isinstance(customer, str) or not customer.strip():
                        continue
                    customer_name = customer.strip()
                    customer_name_key = norm(customer_name)
                    if (
                        customer_name_key in {
                            "zebra", "total", "subtotal", "direct", "kso",
                            "jawabarat", "jawatengah", "jawatimur",
                            "jawatengahdantimur", "jabar", "jateng", "jatim",
                            "allarea", "rata2", "area",
                            *(norm(operator) for operator in CUSTOMER_ASSIGNMENTS),
                        }
                        or customer_name_key.startswith("allarea")
                        or customer_name_key.startswith(("target", "prognosa"))
                        or "kursjisdor" in customer_name_key
                    ):
                        continue

                    values = [
                        worksheet.cell(row_number, customer_column + offset).value
                        for offset in range(1, 6)
                    ]
                    if not any(value is not None for value in values):
                        continue
                    missing_values = {
                        index for index, value in enumerate(values) if value is None
                    }
                    raw = [
                        float(value) if isinstance(value, (int, float)) else 0.0
                        for value in values
                    ]
                    if 0 in missing_values and any(raw[index] for index in (1, 3, 4)):
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Volume customer {customer_name} pada sheet {title}, "
                                f"baris {row_number} tidak memiliki hasil formula tersimpan."
                            ),
                        )
                    if 1 in missing_values and raw[3] > 0 and raw[2] <= 0:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"MMBTU customer {customer_name} pada sheet {title}, "
                                f"baris {row_number} tidak dapat dipastikan dari workbook."
                            ),
                        )
                    if 3 in missing_values and raw[4] > 0 and not exchange_rate:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Total USD customer {customer_name} pada sheet {title}, "
                                f"baris {row_number} tidak dapat dihitung tanpa kurs JISDOR."
                            ),
                        )
                    if 4 in missing_values and raw[3] > 0 and not exchange_rate:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Total Rupiah customer {customer_name} pada sheet {title}, "
                                f"baris {row_number} tidak dapat dihitung tanpa kurs JISDOR."
                            ),
                        )
                    values = list(values)
                    for index in (0, 1, 3, 4):
                        if values[index] is None:
                            values[index] = 0
                    if values[2] is None:
                        values[2] = 0
                    if not all(
                        isinstance(value, (int, float))
                        and math.isfinite(float(value))
                        and float(value) >= 0
                        for value in values
                    ):
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"Nilai customer {customer_name} pada sheet {title}, "
                                f"baris {row_number} tidak lengkap. Simpan ulang workbook "
                                "di Excel agar hasil formula tersedia."
                            ),
                        )

                    sm3, mmbtu, price, total_usd, rupiah = map(float, values)
                    if 3 in missing_values and rupiah > 0 and exchange_rate:
                        total_usd = rupiah / exchange_rate
                    if 4 in missing_values and total_usd > 0 and exchange_rate:
                        rupiah = total_usd * exchange_rate
                    if mmbtu <= 0 and total_usd > 0 and price > 0:
                        mmbtu = total_usd / price
                    if price <= 0 and mmbtu > 0 and total_usd > 0:
                        price = total_usd / mmbtu
                    price_unit = "USD_MMBTU"
                    price_rp = 0.0
                    if price <= 0 and rupiah > 0 and sm3 > 0:
                        price_unit = "IDR_SM3"
                        price_rp = rupiah / sm3
                    detail_entries.append({
                        "customer": customer_name,
                        "region": block_region,
                        "price_unit": price_unit,
                        "price_usd_per_mmbtu": price if price_unit == "USD_MMBTU" else 0.0,
                        "price_rp_per_sm3": price_rp,
                        "sm3_override": sm3,
                        "mmbtu_override": mmbtu,
                        "total_usd_override": total_usd,
                        "rupiah_override": rupiah,
                        "include_in_summary": not (
                            (month_number >= 9 and block_region == "JAWA TIMUR")
                            or (month_number == 6 and customer_name_key == "ksnranca")
                        ),
                    })

            if not detail_entries:
                raise HTTPException(
                    status_code=400,
                    detail=f"Data customer tidak ditemukan pada sheet {title}.",
                )

            summary_average_column, summary_rupiah_column = (
                (22, 24) if is_three_region_layout else (16, 18)
            )
            summary_average = worksheet.cell(1, summary_average_column).value
            summary_rupiah = worksheet.cell(1, summary_rupiah_column).value
            if not all(
                isinstance(value, (int, float))
                and math.isfinite(float(value))
                and float(value) >= 0
                for value in (summary_average, summary_rupiah)
            ) or not float(summary_average):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Ringkasan Average Price pada sheet {title} tidak tersedia. "
                        "Simpan ulang workbook di Excel agar hasil formula tersedia."
                    ),
                )

            summary_rupiah = float(summary_rupiah)
            summary_average = float(summary_average)
            months.append({
                "month": f"{year:04d}-{month_number:02d}",
                "entries": detail_entries,
                "exchange_rate": (
                    exchange_rate
                    if exchange_rate is not None
                    else (
                        sum(entry["rupiah_override"] for entry in detail_entries)
                        / sum(entry["total_usd_override"] for entry in detail_entries)
                        if sum(entry["total_usd_override"] for entry in detail_entries) > 0
                        else 0.0
                    )
                ),
                "summary_sm3": summary_rupiah / summary_average,
                "summary_rupiah": summary_rupiah,
                "summary_average_price": summary_average,
            })
    finally:
        workbook.close()

    if not months:
        raise HTTPException(
            status_code=400,
            detail="Workbook tidak memiliki sheet AVG bulanan yang didukung.",
        )
    if len({month["month"] for month in months}) != len(months):
        raise HTTPException(
            status_code=400,
            detail="Workbook memiliki lebih dari satu sheet untuk bulan yang sama.",
        )
    return {"filename": filename, "months": months}


@app.post("/api/monthly-average-price/workbook-import")
async def import_monthly_average_price_workbook(
    request: Request,
    file: UploadFile = File(...),
):
    require_admin(request)
    filename = Path(file.filename or "average-price.xlsx").name
    if Path(filename).suffix.lower() not in {".xlsx", ".xlsm"}:
        raise HTTPException(status_code=400, detail="Gunakan file Excel .xlsx atau .xlsm.")
    content = await file.read()
    if len(content) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Ukuran file maksimal 30 MB.")

    parsed_workbook = parse_monthly_average_price_workbook(content, filename)
    timestamp = datetime.now().isoformat(timespec="seconds")
    total_rows = 0
    imported_months = []
    with db() as con:
        customer_rows = con.execute(
            "SELECT customer_key,customer_name,operator FROM customers"
        ).fetchall()
        customers_by_canonical_key = {}
        for customer in customer_rows:
            key = canonical_average_price_customer_key(customer["customer_key"])
            customers_by_canonical_key.setdefault(key, []).append(customer)

        prepared_months = []
        unmatched_customers = set()
        for month_data in parsed_workbook["months"]:
            prepared_entries = {}
            for entry in month_data["entries"]:
                source_key = canonical_average_price_customer_key(entry["customer"])
                matches = customers_by_canonical_key.get(source_key, [])
                exact_matches = [
                    customer for customer in matches
                    if norm(customer["customer_key"]) == source_key
                ]
                if exact_matches:
                    matches = exact_matches
                if len(matches) > 1:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Customer {entry['customer']} cocok dengan lebih dari satu "
                            "customer master. Perbaiki pemetaan sebelum impor."
                        ),
                    )
                if not matches:
                    unmatched_customers.add(entry["customer"])
                    continue

                customer = matches[0]
                customer_key = customer["customer_key"]
                region = entry["region"]
                prepared = prepared_entries.get(customer_key)
                if prepared:
                    prepared["sm3_override"] += entry["sm3_override"]
                    prepared["mmbtu_override"] += entry["mmbtu_override"]
                    prepared["total_usd_override"] += entry["total_usd_override"]
                    prepared["rupiah_override"] += entry["rupiah_override"]
                    if prepared["region"] != region:
                        prepared["region"] = "JAWA TENGAH DAN TIMUR"
                    prepared["include_in_summary"] = (
                        prepared["include_in_summary"] and entry["include_in_summary"]
                    )
                    prepared["price_usd_per_mmbtu"] = (
                        prepared["total_usd_override"] / prepared["mmbtu_override"]
                        if prepared["mmbtu_override"] > 0
                        else 0.0
                    )
                else:
                    prepared_entries[customer_key] = {
                        **entry,
                        "customer_key": customer_key,
                        "region": (
                            REGION_BY_CUSTOMER.get(customer_key)
                            or entry["region"]
                        ),
                        "operator": customer["operator"],
                    }
            if unmatched_customers:
                continue

            operator_totals = {}
            for entry in prepared_entries.values():
                operator_totals.setdefault(entry["operator"], [0.0, 0.0])
                operator_totals[entry["operator"]][0] += entry["sm3_override"]
                operator_totals[entry["operator"]][1] += entry["mmbtu_override"]
            prepared_months.append((month_data, prepared_entries, operator_totals))

        if unmatched_customers:
            names = ", ".join(sorted(unmatched_customers))
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Customer pada workbook belum cocok dengan master: {names}. "
                    "Tambahkan atau perbaiki pemetaan customer sebelum mengimpor."
                ),
            )

        for month_data, entries, operator_totals in prepared_months:
            month_start = f"{month_data['month']}-01"
            con.execute(
                "DELETE FROM monthly_average_price_inputs WHERE month_start=%s",
                (month_start,),
            )
            for operator in OPERATORS:
                sm3_total, mmbtu_total = operator_totals.get(operator, (0.0, 0.0))
                factor = sm3_total / mmbtu_total if mmbtu_total > 0 else 0.0
                con.execute(
                    "INSERT INTO monthly_average_price_operator_factors("
                    "month_start,operator,sm3_per_mmbtu,updated_at) "
                    "VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                    "sm3_per_mmbtu=VALUES(sm3_per_mmbtu),updated_at=VALUES(updated_at)",
                    (month_start, operator, factor, timestamp),
                )
            con.execute(
                "INSERT INTO monthly_average_price_exchange_rates("
                "month_start,exchange_rate,updated_at) VALUES(%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE exchange_rate=VALUES(exchange_rate),"
                "updated_at=VALUES(updated_at)",
                (month_start, month_data["exchange_rate"], timestamp),
            )
            for entry in entries.values():
                con.execute(
                    "INSERT INTO monthly_average_price_inputs("
                    "month_start,customer_key,region,price_unit,price_usd_per_mmbtu,"
                    "price_rp_per_sm3,sm3_override,mmbtu_override,total_usd_override,"
                    "rupiah_override,include_in_summary,updated_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        month_start,
                        entry["customer_key"],
                        entry["region"],
                        entry["price_unit"],
                        entry["price_usd_per_mmbtu"],
                        entry["price_rp_per_sm3"],
                        entry["sm3_override"],
                        entry["mmbtu_override"],
                        entry["total_usd_override"],
                        entry["rupiah_override"],
                        entry["include_in_summary"],
                        timestamp,
                    ),
                )
            customer_keys = sorted(norm(entry["customer_key"]) for entry in entries.values())
            con.execute(
                "INSERT INTO monthly_average_price_workbook_imports("
                "month_start,filename,imported_at,customer_keys_json,summary_sm3,"
                "summary_rupiah,summary_average_price) VALUES(%s,%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE filename=VALUES(filename),"
                "imported_at=VALUES(imported_at),customer_keys_json=VALUES(customer_keys_json),"
                "summary_sm3=VALUES(summary_sm3),summary_rupiah=VALUES(summary_rupiah),"
                "summary_average_price=VALUES(summary_average_price)",
                (
                    month_start,
                    parsed_workbook["filename"],
                    timestamp,
                    json.dumps(customer_keys),
                    month_data["summary_sm3"],
                    month_data["summary_rupiah"],
                    month_data["summary_average_price"],
                ),
            )
            imported_months.append({
                "month": month_data["month"],
                "rows": len(entries),
                "average_price": month_data["summary_average_price"],
            })
            total_rows += len(entries)

    return {
        "ok": True,
        "filename": parsed_workbook["filename"],
        "imported_months": imported_months,
        "imported_rows": total_rows,
        "source_priority": "workbook",
    }


@app.get("/api/monthly-average-price/sheet-import")
def import_monthly_average_price_sheet(request: Request, month: str):
    require_admin(request)
    try:
        month_start = date.fromisoformat(f"{month}-01")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Format bulan harus YYYY-MM.") from exc
    if month_start.strftime("%Y-%m") != month:
        raise HTTPException(status_code=400, detail="Format bulan harus YYYY-MM.")

    credential_path = Path(ISSUE_GOOGLE_SERVICE_ACCOUNT_FILE)
    if not credential_path.is_file() or credential_path.stat().st_size == 0:
        values = fetch_public_average_price_sheet_values()
        source_title = AVERAGE_PRICE_SHEET_TITLE
    else:
        try:
            service_account_info = json.loads(credential_path.read_text(encoding="utf-8"))
            credentials = Credentials.from_service_account_info(
                service_account_info,
                scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
            )
        except (OSError, ValueError, TypeError, KeyError, GoogleAuthError) as exc:
            raise HTTPException(
                status_code=500,
                detail="Kredensial Google service account tidak valid atau belum lengkap.",
            ) from exc

        api_base = f"https://sheets.googleapis.com/v4/spreadsheets/{AVERAGE_PRICE_SHEET_ID}"
        session = AuthorizedSession(credentials)
        try:
            metadata_response = session.get(
                f"{api_base}?fields=sheets(properties(sheetId,title))",
                timeout=15,
            )
            if metadata_response.status_code in {401, 403}:
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Google Sheets API menolak akses service account. Aktifkan Google Sheets API "
                        "dan bagikan spreadsheet sebagai Viewer ke client_email pada kredensial server."
                    ),
                )
            if metadata_response.status_code == 404:
                raise HTTPException(
                    status_code=502,
                    detail="Spreadsheet Average Price tidak ditemukan. Periksa AVERAGE_PRICE_SHEET_ID.",
                )
            metadata_response.raise_for_status()
            metadata = metadata_response.json()
            if not isinstance(metadata, dict):
                raise HTTPException(status_code=502, detail="Respons metadata Google Sheets tidak valid.")
            sheet = next(
                (
                    item.get("properties", {})
                    for item in metadata.get("sheets", [])
                    if isinstance(item, dict)
                    and str(item.get("properties", {}).get("sheetId")) == AVERAGE_PRICE_SHEET_GID
                ),
                None,
            )
            if not sheet or not sheet.get("title"):
                raise HTTPException(
                    status_code=502,
                    detail="Tab Google Sheets dengan AVERAGE_PRICE_SHEET_GID tersebut tidak ditemukan.",
                )

            encoded_range = quote(f"'{sheet['title']}'!A1:O5000", safe="")
            values_response = session.get(
                f"{api_base}/values/{encoded_range}?valueRenderOption=FORMATTED_VALUE",
                timeout=15,
            )
            if values_response.status_code in {401, 403}:
                raise HTTPException(
                    status_code=502,
                    detail="Service account tidak dapat membaca tab harga. Pastikan akses Viewer sudah diberikan.",
                )
            values_response.raise_for_status()
            values_payload = values_response.json()
            if not isinstance(values_payload, dict):
                raise HTTPException(status_code=502, detail="Respons data Google Sheets tidak valid.")
            values = values_payload.get("values", [])
            source_title = str(sheet["title"])
        except HTTPException:
            raise
        except (RequestException, GoogleAuthError) as exc:
            raise HTTPException(
                status_code=502,
                detail="Google Sheets API tidak merespons. Coba tarik harga kembali beberapa saat lagi.",
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail="Google Sheets API mengembalikan respons JSON yang tidak valid.",
            ) from exc

    entries = parse_average_price_sheet_values(values, month)
    return {"month": month, "entries": entries, "source": source_title}


@app.post("/api/monthly-average-price/sheet-sync")
async def sync_monthly_average_price_sheet(request: Request):
    require_admin(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format data sinkronisasi tidak valid.")
    month = str(payload.get("month", "")).strip()
    mappings = payload.get("customer_mappings", [])
    try:
        month_start = date.fromisoformat(f"{month}-01")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Format bulan harus YYYY-MM.") from exc
    if month_start.strftime("%Y-%m") != month or not isinstance(mappings, list):
        raise HTTPException(status_code=400, detail="Bulan atau pemetaan customer tidak valid.")

    imported = import_monthly_average_price_sheet(request, month)
    entries = imported["entries"]
    sheet_customers = {
        canonical_average_price_customer_key(entry["customer"])
        for entry in entries
    }
    normalized_mappings = {}
    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise HTTPException(status_code=400, detail="Format pemetaan customer tidak valid.")
        customer_name = str(mapping.get("customer", "")).strip()
        customer_key, customer_name, operator = normalize_customer_mapping(
            customer_name,
            mapping.get("operator"),
        )
        region = str(mapping.get("region", "")).strip().upper()
        if region not in {"JAWA BARAT", "JAWA TENGAH", "JAWA TIMUR", "JAWA TENGAH DAN TIMUR"}:
            raise HTTPException(status_code=400, detail="Wilayah customer baru tidak valid.")
        source_key = canonical_average_price_customer_key(customer_name)
        if source_key not in sheet_customers:
            raise HTTPException(
                status_code=400,
                detail=f"Customer {customer_name} tidak ditemukan pada sheet harga bulan ini.",
            )
        if source_key in normalized_mappings:
            raise HTTPException(status_code=400, detail=f"Pemetaan duplikat untuk {customer_name}.")
        normalized_mappings[source_key] = {
            "customer_key": customer_key,
            "customer_name": customer_name,
            "operator": operator,
            "region": region,
        }

    timestamp = datetime.now().isoformat(timespec="seconds")
    unmatched_customers = []
    imported_count = 0
    deactivated_count = 0
    created_customers = []
    sheet_customer_keys = set(sheet_customers)
    with db() as con:
        customer_rows = con.execute(
            "SELECT customer_key,customer_name,operator FROM customers"
        ).fetchall()
        customers_by_canonical_key = {}
        for customer in customer_rows:
            key = canonical_average_price_customer_key(customer["customer_key"])
            customers_by_canonical_key.setdefault(key, []).append(customer)

        for entry in entries:
            source_key = canonical_average_price_customer_key(entry["customer"])
            if source_key in AVERAGE_PRICE_EXCLUDED_CUSTOMER_KEYS:
                continue
            matching_customers = customers_by_canonical_key.get(source_key, [])
            if entry["price_unit"] == "IDR_USD_MULTIPLIER":
                priced_customers = []
                for candidate in matching_customers:
                    candidate_input = con.execute(
                        "SELECT price_usd_per_mmbtu FROM monthly_average_price_inputs "
                        "WHERE month_start=%s AND customer_key=%s",
                        (month_start.isoformat(), candidate["customer_key"]),
                    ).fetchone()
                    if candidate_input and float(candidate_input["price_usd_per_mmbtu"] or 0) > 0:
                        priced_customers.append(candidate)
                if priced_customers:
                    matching_customers = priced_customers
            else:
                exact_customers = [
                    customer
                    for customer in matching_customers
                    if norm(customer["customer_key"]) == source_key
                ]
                if exact_customers:
                    matching_customers = exact_customers
            if len(matching_customers) > 1:
                raise HTTPException(
                    status_code=409,
                    detail=f"Nama customer {entry['customer']} cocok dengan lebih dari satu customer master.",
                )
            if matching_customers:
                customer = matching_customers[0]
                customer_key = customer["customer_key"]
                sheet_customer_keys.add(norm(customer_key))
                region = (
                    REGION_BY_CUSTOMER.get(customer_key)
                    or REGION_BY_OPERATOR.get(customer["operator"], "")
                )
            else:
                if not entry["active"] and source_key not in normalized_mappings:
                    continue
                mapping = normalized_mappings.get(source_key)
                if not mapping:
                    unmatched_customers.append(entry["customer"])
                    continue
                existing = con.execute(
                    "SELECT customer_key,operator FROM customers WHERE customer_key=%s",
                    (mapping["customer_key"],),
                ).fetchone()
                if existing and existing["operator"] != mapping["operator"]:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Customer {mapping['customer_name']} sudah terdaftar dengan operator berbeda. "
                            "Hubungi Admin untuk memperbaiki mapping."
                        ),
                    )
                if not existing:
                    con.execute(
                        "INSERT INTO customers(customer_key,customer_name,operator) VALUES(%s,%s,%s)",
                        (
                            mapping["customer_key"],
                            mapping["customer_name"],
                            mapping["operator"],
                        ),
                    )
                    created_customers.append(mapping["customer_name"])
                customer = {
                    "customer_key": mapping["customer_key"],
                    "customer_name": mapping["customer_name"],
                    "operator": mapping["operator"],
                }
                customer_key = mapping["customer_key"]
                sheet_customer_keys.add(norm(customer_key))
                region = mapping["region"]
                customers_by_canonical_key[source_key] = [customer]

            price_unit = entry["price_unit"]
            rupiah_multiplier = None
            if price_unit == "IDR_USD_MULTIPLIER":
                existing_input = con.execute(
                    "SELECT price_usd_per_mmbtu FROM monthly_average_price_inputs "
                    "WHERE month_start=%s AND customer_key=%s",
                    (month_start.isoformat(), customer_key),
                ).fetchone()
                price_unit = "USD_MMBTU"
                price_usd = (
                    float(existing_input["price_usd_per_mmbtu"] or 0)
                    if entry["active"] and existing_input
                    else 0
                )
                price_rp = 0
                rupiah_multiplier = entry["price"] if entry["active"] else None
            else:
                price_usd = (
                    entry["price"]
                    if entry["active"] and price_unit == "USD_MMBTU"
                    else 0
                )
                price_rp = (
                    entry["price"]
                    if entry["active"] and price_unit == "IDR_SM3"
                    else 0
                )
            con.execute(
                "INSERT INTO monthly_average_price_inputs("
                "month_start,customer_key,region,price_unit,price_usd_per_mmbtu,"
                "price_rp_per_sm3,rupiah_multiplier,include_in_summary,updated_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,1,%s) "
                "ON DUPLICATE KEY UPDATE price_unit=VALUES(price_unit),"
                "price_usd_per_mmbtu=VALUES(price_usd_per_mmbtu),"
                "price_rp_per_sm3=VALUES(price_rp_per_sm3),"
                "rupiah_multiplier=VALUES(rupiah_multiplier),"
                "total_usd_override=NULL,rupiah_override=NULL,updated_at=VALUES(updated_at)",
                (
                    month_start.isoformat(),
                    customer_key,
                    region,
                    price_unit,
                    price_usd,
                    price_rp,
                    rupiah_multiplier,
                    timestamp,
                ),
            )
            imported_count += 1
            deactivated_count += int(not entry["active"])

        legacy_workbook = con.execute(
            "SELECT month_start FROM monthly_average_price_workbook_imports WHERE month_start=%s",
            (month_start.isoformat(),),
        ).fetchone()
        if legacy_workbook:
            con.execute(
                "UPDATE monthly_average_price_inputs SET sm3_override=NULL,"
                "mmbtu_override=NULL,total_usd_override=NULL,rupiah_override=NULL,"
                "include_in_summary=1 WHERE month_start=%s",
                (month_start.isoformat(),),
            )
            con.execute(
                "DELETE FROM monthly_average_price_workbook_imports WHERE month_start=%s",
                (month_start.isoformat(),),
            )

    return {
        "month": month,
        "source": imported["source"],
        "imported": imported_count,
        "deactivated": deactivated_count,
        "created_customers": created_customers,
        "unmatched_customers": unmatched_customers,
        "sheet_customer_keys": sorted(sheet_customer_keys),
    }


@app.get("/api/monthly-average-price")
def monthly_average_price(request: Request, month: str):
    require_login(request)
    try:
        month_start = date.fromisoformat(f"{month}-01")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Format bulan harus YYYY-MM.") from exc
    if month_start.strftime("%Y-%m") != month:
        raise HTTPException(status_code=400, detail="Format bulan harus YYYY-MM.")
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    with db() as con:
        sales_rows = con.execute(
            """
            SELECT c.customer_key,c.customer_name,c.operator,
                   COALESCE(SUM(s.so),0) AS so_sm3,
                   COALESCE(SUM(s.actual),0) AS actual_sm3,
                   COALESCE(price_inputs.region,'') AS region,
                   COALESCE(price_inputs.price_unit,'USD_MMBTU') AS price_unit,
                   COALESCE(price_inputs.price_usd_per_mmbtu,0) AS price_usd_per_mmbtu,
                   COALESCE(price_inputs.price_rp_per_sm3,0) AS price_rp_per_sm3,
                   price_inputs.rupiah_multiplier,
                   price_inputs.sm3_override,
                   price_inputs.mmbtu_override,
                   price_inputs.total_usd_override,
                   price_inputs.rupiah_override,
                   COALESCE(price_inputs.include_in_summary,1) AS include_in_summary,
                   COALESCE(operator_factors.sm3_per_mmbtu,0) AS sm3_per_mmbtu
            FROM customers c
            LEFT JOIN sales s
              ON s.customer_key=c.customer_key
             AND s.report_date >= %s AND s.report_date < %s
            LEFT JOIN monthly_average_price_inputs price_inputs
              ON price_inputs.month_start=%s
             AND price_inputs.customer_key=c.customer_key
            LEFT JOIN monthly_average_price_operator_factors operator_factors
              ON operator_factors.month_start=%s
             AND operator_factors.operator=c.operator
            WHERE s.customer_key IS NOT NULL OR price_inputs.customer_key IS NOT NULL
            GROUP BY c.customer_key,c.customer_name,c.operator,
                     price_inputs.region,price_inputs.price_unit,
                     price_inputs.price_usd_per_mmbtu,price_inputs.price_rp_per_sm3,
                     price_inputs.rupiah_multiplier,
                     price_inputs.sm3_override,price_inputs.mmbtu_override,
                     price_inputs.total_usd_override,price_inputs.rupiah_override,
                     price_inputs.include_in_summary,
                     operator_factors.sm3_per_mmbtu
            ORDER BY c.operator,c.customer_name
            """,
            (
                month_start.isoformat(),
                next_month.isoformat(),
                month_start.isoformat(),
                month_start.isoformat(),
            ),
        ).fetchall()
        exchange = con.execute(
            "SELECT exchange_rate FROM monthly_average_price_exchange_rates WHERE month_start=%s",
            (month_start.isoformat(),),
        ).fetchone()
        factor_rows = con.execute(
            "SELECT operator,sm3_per_mmbtu FROM monthly_average_price_operator_factors "
            "WHERE month_start=%s",
            (month_start.isoformat(),),
        ).fetchall()
        target_rows = con.execute(
            "SELECT region,target_price_rp_sm3 FROM monthly_average_price_targets "
            "WHERE month_start=%s",
            (month_start.isoformat(),),
        ).fetchall()
        workbook_import = con.execute(
            "SELECT customer_keys_json FROM monthly_average_price_workbook_imports "
            "WHERE month_start=%s",
            (month_start.isoformat(),),
        ).fetchone()
    exchange_rate = float(exchange["exchange_rate"] or 0) if exchange else 0.0

    legacy_workbook_customer_keys = set()
    if workbook_import:
        imported_customer_keys = json.loads(workbook_import["customer_keys_json"])
        if not isinstance(imported_customer_keys, list) or any(
            not isinstance(key, str) for key in imported_customer_keys
        ):
            raise HTTPException(
                status_code=500,
                detail="Daftar customer pada impor workbook tersimpan dalam format tidak valid.",
            )
        legacy_workbook_customer_keys = set(imported_customer_keys)

    rows = []
    totals = {"sm3": 0.0, "mmbtu": 0.0, "usd": 0.0, "rupiah": 0.0}
    for row in sales_rows:
        if canonical_average_price_customer_key(row["customer_key"]) in AVERAGE_PRICE_EXCLUDED_CUSTOMER_KEYS:
            continue
        so_sm3 = float(row["so_sm3"] or 0)
        actual_sm3 = float(row["actual_sm3"] or 0)
        is_legacy_workbook_row = row["customer_key"] in legacy_workbook_customer_keys
        sm3_override = None
        mmbtu_override = None
        total_usd_override = None
        rupiah_override = None
        sm3 = actual_sm3
        factor = float(row["sm3_per_mmbtu"] or 0)
        price_unit = row.get("price_unit") or "USD_MMBTU"
        price = float(row["price_usd_per_mmbtu"] or 0)
        price_rp = float(row.get("price_rp_per_sm3") or 0)
        rupiah_multiplier = float(row.get("rupiah_multiplier") or 0)
        is_valid_price = has_valid_average_price(
            price_unit,
            price,
            price_rp,
            factor,
            exchange_rate,
            mmbtu_override,
            total_usd_override,
            rupiah_override,
            rupiah_multiplier,
        )
        mmbtu, total_usd, rupiah = calculate_average_price(
            sm3,
            factor,
            price_unit,
            price,
            price_rp,
            exchange_rate,
            mmbtu_override,
            total_usd_override,
            rupiah_override,
            rupiah_multiplier,
        )
        include_in_summary = (
            True if is_legacy_workbook_row else bool(row.get("include_in_summary", True))
        )
        region_key = norm(row.get("region") or "")
        customer_name_key = norm(row["customer_name"])
        if (
            (month_start.month >= 9 and region_key == "jawatimur")
            or (month_start.month == 6 and customer_name_key == "ksnranca")
        ):
            include_in_summary = False
        if is_valid_price and include_in_summary:
            totals["sm3"] += sm3
            totals["mmbtu"] += mmbtu
            totals["usd"] += total_usd
            totals["rupiah"] += rupiah
        rows.append({
            "customer_key": row["customer_key"],
            "customer": row["customer_name"],
            "operator": row["operator"],
            "region": row["region"] or "",
            "price_unit": price_unit,
            "so_sm3": so_sm3,
            "actual_sm3": actual_sm3,
            "sm3": sm3,
            "sm3_per_mmbtu": factor,
            "volume_mmbtu": mmbtu,
            "price_usd_per_mmbtu": price,
            "price_rp_per_sm3": price_rp,
            "rupiah_multiplier": rupiah_multiplier,
            "sm3_override": sm3_override,
            "mmbtu_override": mmbtu_override,
            "total_usd_override": total_usd_override,
            "rupiah_override": rupiah_override,
            "total_usd": total_usd,
            "exchange_rate": exchange_rate,
            "has_valid_price": is_valid_price,
            "include_in_summary": include_in_summary,
            "rupiah": rupiah,
        })
    totals["average_price_rp_sm3"] = (
        totals["rupiah"] / totals["sm3"] if totals["sm3"] else 0.0
    )
    return {
        "month": month,
        "exchange_rate": exchange_rate,
        "source": "system",
        "workbook_import": None,
        "workbook_customer_keys": [],
        "operator_factors": {
            row["operator"]: float(row["sm3_per_mmbtu"] or 0)
            for row in factor_rows
        },
        "targets": {
            row["region"]: float(row["target_price_rp_sm3"])
            for row in target_rows
        },
        "rows": rows,
        "totals": totals,
    }


@app.get("/api/monthly-average-price-range")
def monthly_average_price_range(request: Request, start_date: str, end_date: str):
    require_home_access(request)
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Tanggal harus berformat YYYY-MM-DD.") from exc
    if start > end:
        raise HTTPException(status_code=400, detail="Tanggal awal tidak boleh melewati tanggal akhir.")

    with db() as con:
        sales_rows = con.execute(
            """
            SELECT c.customer_key,c.customer_name,c.operator,
                   DATE_FORMAT(s.report_date, '%%Y-%%m') AS period,
                   SUM(s.so) AS so_sm3,
                   SUM(s.actual) AS actual_sm3,
                   COALESCE(price_inputs.region,'') AS region,
                   COALESCE(price_inputs.price_unit,'USD_MMBTU') AS price_unit,
                   COALESCE(price_inputs.price_usd_per_mmbtu,0) AS price_usd_per_mmbtu,
                   COALESCE(price_inputs.price_rp_per_sm3,0) AS price_rp_per_sm3,
                   price_inputs.rupiah_multiplier,
                   price_inputs.sm3_override,
                   price_inputs.mmbtu_override,
                   price_inputs.total_usd_override,
                   price_inputs.rupiah_override,
                   COALESCE(price_inputs.include_in_summary,1) AS include_in_summary,
                   COALESCE(operator_factors.sm3_per_mmbtu,0) AS sm3_per_mmbtu,
                   COALESCE(exchange_rates.exchange_rate,0) AS exchange_rate
            FROM sales s
            JOIN customers c ON c.customer_key=s.customer_key
            LEFT JOIN monthly_average_price_inputs price_inputs
              ON price_inputs.month_start=DATE_FORMAT(s.report_date, '%%Y-%%m-01')
             AND price_inputs.customer_key=c.customer_key
            LEFT JOIN monthly_average_price_operator_factors operator_factors
              ON operator_factors.month_start=DATE_FORMAT(s.report_date, '%%Y-%%m-01')
             AND operator_factors.operator=c.operator
            LEFT JOIN monthly_average_price_exchange_rates exchange_rates
              ON exchange_rates.month_start=DATE_FORMAT(s.report_date, '%%Y-%%m-01')
            WHERE s.report_date BETWEEN %s AND %s
            GROUP BY c.customer_key,c.customer_name,c.operator,period,
                     price_inputs.region,price_inputs.price_unit,
                     price_inputs.price_usd_per_mmbtu,price_inputs.price_rp_per_sm3,
                     price_inputs.rupiah_multiplier,
                     price_inputs.sm3_override,price_inputs.mmbtu_override,
                     price_inputs.total_usd_override,price_inputs.rupiah_override,
                     price_inputs.include_in_summary,
                     operator_factors.sm3_per_mmbtu,exchange_rates.exchange_rate
            ORDER BY period,c.operator,c.customer_name
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        input_rows = con.execute(
            """
            SELECT c.customer_key,c.customer_name,c.operator,
                   DATE_FORMAT(price_inputs.month_start, '%%Y-%%m') AS period,
                   price_inputs.region,price_inputs.price_unit,
                   price_inputs.price_usd_per_mmbtu,price_inputs.price_rp_per_sm3,
                   price_inputs.rupiah_multiplier,
                   price_inputs.sm3_override,price_inputs.mmbtu_override,
                   price_inputs.total_usd_override,price_inputs.rupiah_override,
                   price_inputs.include_in_summary,
                   COALESCE(operator_factors.sm3_per_mmbtu,0) AS sm3_per_mmbtu,
                   COALESCE(exchange_rates.exchange_rate,0) AS exchange_rate,
                   workbook_import.summary_sm3 AS workbook_summary_sm3,
                   workbook_import.summary_rupiah AS workbook_summary_rupiah
            FROM monthly_average_price_inputs price_inputs
            JOIN customers c ON c.customer_key=price_inputs.customer_key
            LEFT JOIN monthly_average_price_operator_factors operator_factors
              ON operator_factors.month_start=price_inputs.month_start
             AND operator_factors.operator=c.operator
            LEFT JOIN monthly_average_price_exchange_rates exchange_rates
              ON exchange_rates.month_start=price_inputs.month_start
            LEFT JOIN monthly_average_price_workbook_imports workbook_import
              ON workbook_import.month_start=price_inputs.month_start
            WHERE price_inputs.month_start >= %s AND price_inputs.month_start <= %s
            ORDER BY price_inputs.month_start,c.operator,c.customer_name
            """,
            (
                date(start.year, start.month, 1).isoformat(),
                date(end.year, end.month, 1).isoformat(),
            ),
        ).fetchall()

    totals = {"sm3": 0.0, "mmbtu": 0.0, "usd": 0.0, "rupiah": 0.0}
    rows = []
    rows_by_period_customer = {
        (row["period"], row["customer_key"]): row
        for row in sales_rows
        if canonical_average_price_customer_key(row["customer_key"]) not in AVERAGE_PRICE_EXCLUDED_CUSTOMER_KEYS
    }
    legacy_workbook_months = {
        row["period"]
        for row in input_rows
        if row.get("workbook_summary_sm3") is not None
    }
    for row in input_rows:
        if canonical_average_price_customer_key(row["customer_key"]) in AVERAGE_PRICE_EXCLUDED_CUSTOMER_KEYS:
            continue
        period_start = date.fromisoformat(f"{row['period']}-01")
        next_period_start = (
            date(period_start.year + 1, 1, 1)
            if period_start.month == 12
            else date(period_start.year, period_start.month + 1, 1)
        )
        period_end = next_period_start - timedelta(days=1)
        if (
            start <= period_start
            and end >= period_end
            and (row["period"], row["customer_key"]) not in rows_by_period_customer
        ):
            rows_by_period_customer[(row["period"], row["customer_key"])] = {
                **row,
                "so_sm3": 0,
                "actual_sm3": 0,
            }

    for row in rows_by_period_customer.values():
        so_sm3 = float(row["so_sm3"] or 0)
        actual_sm3 = float(row["actual_sm3"] or 0)
        period_start = date.fromisoformat(f"{row['period']}-01")
        is_legacy_workbook_month = row["period"] in legacy_workbook_months
        sm3_override = None
        mmbtu_override = None
        total_usd_override = None
        rupiah_override = None
        sm3 = actual_sm3
        factor = float(row["sm3_per_mmbtu"] or 0)
        price_unit = row.get("price_unit") or "USD_MMBTU"
        price = float(row["price_usd_per_mmbtu"] or 0)
        price_rp = float(row.get("price_rp_per_sm3") or 0)
        rupiah_multiplier = float(row.get("rupiah_multiplier") or 0)
        exchange_rate = float(row["exchange_rate"] or 0)
        is_valid_price = has_valid_average_price(
            price_unit,
            price,
            price_rp,
            factor,
            exchange_rate,
            mmbtu_override,
            total_usd_override,
            rupiah_override,
            rupiah_multiplier,
        )
        mmbtu, total_usd, rupiah = calculate_average_price(
            sm3,
            factor,
            price_unit,
            price,
            price_rp,
            exchange_rate,
            mmbtu_override,
            total_usd_override,
            rupiah_override,
            rupiah_multiplier,
        )
        include_in_summary = (
            True
            if is_legacy_workbook_month
            else bool(row.get("include_in_summary", True))
        )
        region_key = norm(row.get("region") or "")
        customer_name_key = norm(row["customer_name"])
        if (
            (period_start.month >= 9 and region_key == "jawatimur")
            or (period_start.month == 6 and customer_name_key == "ksnranca")
        ):
            include_in_summary = False
        if is_valid_price and include_in_summary:
            totals["sm3"] += sm3
            totals["mmbtu"] += mmbtu
            totals["usd"] += total_usd
            totals["rupiah"] += rupiah
        rows.append({
            "month": row["period"],
            "customer_key": row["customer_key"],
            "customer": row["customer_name"],
            "operator": row["operator"],
            "region": row["region"] or "",
            "price_unit": price_unit,
            "so_sm3": so_sm3,
            "actual_sm3": actual_sm3,
            "sm3": sm3,
            "sm3_per_mmbtu": factor,
            "volume_mmbtu": mmbtu,
            "price_usd_per_mmbtu": price,
            "price_rp_per_sm3": price_rp,
            "rupiah_multiplier": rupiah_multiplier,
            "sm3_override": sm3_override,
            "mmbtu_override": mmbtu_override,
            "total_usd_override": total_usd_override,
            "rupiah_override": rupiah_override,
            "total_usd": total_usd,
            "exchange_rate": exchange_rate,
            "has_valid_price": is_valid_price,
            "include_in_summary": include_in_summary,
            "rupiah": rupiah,
        })
    totals["average_price_rp_sm3"] = (
        totals["rupiah"] / totals["sm3"] if totals["sm3"] else 0.0
    )
    if not is_admin(request) and request.session.get("role") != "user":
        region_totals = {}
        valid_price_count = 0
        for row in rows:
            region = row["region"] or "Belum ditentukan"
            regional = region_totals.setdefault(
                region,
                {"region": region, "so_sm3": 0.0, "actual_sm3": 0.0},
            )
            regional["so_sm3"] += row["so_sm3"]
            regional["actual_sm3"] += row["actual_sm3"]
            valid_price_count += int(
                row["has_valid_price"] and row["include_in_summary"]
            )
        return {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "rows": [],
            "regions": list(region_totals.values()),
            "valid_price_count": valid_price_count,
            "totals": totals,
        }
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "rows": rows,
        "totals": totals,
    }


@app.post("/api/monthly-average-price")
async def save_monthly_average_price(request: Request):
    require_admin(request)
    payload = await request.json()
    month = str(payload.get("month", ""))
    try:
        month_start = date.fromisoformat(f"{month}-01")
        exchange_rate = float(payload.get("exchange_rate") or 0)
        factors = payload.get("operator_factors", {})
        entries = payload.get("entries", [])
        targets = payload.get("targets", {})
        if (
            month_start.strftime("%Y-%m") != month
            or not isinstance(factors, dict)
            or not isinstance(entries, list)
            or not isinstance(targets, dict)
        ):
            raise ValueError
        normalized_factors = {}
        for operator in OPERATORS:
            factor = float(factors.get(operator) or 0)
            if not math.isfinite(factor) or factor < 0:
                raise ValueError
            normalized_factors[operator] = factor
        if not math.isfinite(exchange_rate) or exchange_rate < 0:
            raise ValueError
        normalized_entries = []
        submitted_customer_keys = set()
        for entry in entries:
            customer_key = str(entry.get("customer_key", "")).strip()
            region = str(entry.get("region", "")).strip()
            price_unit = str(entry.get("price_unit") or "USD_MMBTU").strip()
            if price_unit == "IDR_SM3":
                price_usd = 0.0
                price_rp = float(entry.get("price_rp_per_sm3") or 0)
                rupiah_multiplier = None
            elif price_unit == "USD_MMBTU":
                price_usd = float(entry.get("price_usd_per_mmbtu") or 0)
                price_rp = 0.0
                rupiah_multiplier = entry.get("rupiah_multiplier")
                if rupiah_multiplier is not None:
                    rupiah_multiplier = float(rupiah_multiplier)
            else:
                raise ValueError
            if (
                not customer_key
                or not math.isfinite(price_usd)
                or price_usd < 0
                or not math.isfinite(price_rp)
                or price_rp < 0
                or (
                    rupiah_multiplier is not None
                    and (
                        not math.isfinite(rupiah_multiplier)
                        or rupiah_multiplier < 0
                    )
                )
            ):
                raise ValueError
            if canonical_average_price_customer_key(customer_key) in AVERAGE_PRICE_EXCLUDED_CUSTOMER_KEYS:
                raise HTTPException(
                    status_code=400,
                    detail="Pentawira tidak termasuk dalam Average Price.",
                )
            if customer_key in submitted_customer_keys:
                raise HTTPException(
                    status_code=400,
                    detail=f"Customer dikirim lebih dari sekali: {customer_key}.",
                )
            submitted_customer_keys.add(customer_key)
            overrides = []
            for field in (
                "sm3_override",
                "mmbtu_override",
                "total_usd_override",
                "rupiah_override",
            ):
                value = entry.get(field)
                if value is None or value == "":
                    overrides.append(None)
                    continue
                numeric_value = float(value)
                if not math.isfinite(numeric_value) or numeric_value < 0:
                    raise ValueError
                overrides.append(numeric_value)
            include_in_summary = entry.get("include_in_summary", True)
            if not isinstance(include_in_summary, bool):
                raise ValueError
            normalized_entries.append((
                customer_key,
                region,
                price_unit,
                price_usd,
                price_rp,
                rupiah_multiplier,
                *overrides,
                include_in_summary,
            ))
        allowed_target_regions = {
            "JAWA BARAT", "JAWA TENGAH", "JAWA TIMUR",
            "JAWA_TENGAH_DAN_TIMUR", "ALL_EXCEPT_JATIM",
        }
        normalized_targets = {}
        for region, target in targets.items():
            if region not in allowed_target_regions:
                raise ValueError
            if target is None or target == "":
                normalized_targets[region] = None
                continue
            target_value = float(target)
            if not math.isfinite(target_value) or target_value < 0:
                raise ValueError
            normalized_targets[region] = math.floor(target_value + 0.5)
    except (AttributeError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Bulan dan angka input harus valid dan non-negatif.") from exc

    timestamp = datetime.now().isoformat(timespec="seconds")
    with db() as con:
        for customer_key, *_ in normalized_entries:
            if not con.execute(
                "SELECT customer_key FROM customers WHERE customer_key=%s",
                (customer_key,),
            ).fetchone():
                raise HTTPException(status_code=404, detail=f"Customer tidak ditemukan: {customer_key}.")
        for operator, factor in normalized_factors.items():
            con.execute(
                "INSERT INTO monthly_average_price_operator_factors(month_start,operator,sm3_per_mmbtu,updated_at) "
                "VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                "sm3_per_mmbtu=VALUES(sm3_per_mmbtu),updated_at=VALUES(updated_at)",
                (month_start.isoformat(), operator, factor, timestamp),
            )
        con.execute(
            "INSERT INTO monthly_average_price_exchange_rates(month_start,exchange_rate,updated_at) "
            "VALUES(%s,%s,%s) ON DUPLICATE KEY UPDATE "
            "exchange_rate=VALUES(exchange_rate),updated_at=VALUES(updated_at)",
            (month_start.isoformat(), exchange_rate, timestamp),
        )
        for (
            customer_key,
            region,
            price_unit,
            price_usd,
            price_rp,
            rupiah_multiplier,
            sm3_override,
            mmbtu_override,
            total_usd_override,
            rupiah_override,
            include_in_summary,
        ) in normalized_entries:
            con.execute(
                "INSERT INTO monthly_average_price_inputs("
                "month_start,customer_key,region,price_unit,price_usd_per_mmbtu,"
                "price_rp_per_sm3,rupiah_multiplier,sm3_override,mmbtu_override,total_usd_override,"
                "rupiah_override,include_in_summary,updated_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE region=VALUES(region),price_unit=VALUES(price_unit),"
                "price_usd_per_mmbtu=VALUES(price_usd_per_mmbtu),"
                "price_rp_per_sm3=VALUES(price_rp_per_sm3),"
                "rupiah_multiplier=VALUES(rupiah_multiplier),"
                "sm3_override=VALUES(sm3_override),mmbtu_override=VALUES(mmbtu_override),"
                "total_usd_override=VALUES(total_usd_override),"
                "rupiah_override=VALUES(rupiah_override),"
                "include_in_summary=VALUES(include_in_summary),updated_at=VALUES(updated_at)",
                (
                    month_start.isoformat(),
                    customer_key,
                    region,
                    price_unit,
                    price_usd,
                    price_rp,
                    rupiah_multiplier,
                    sm3_override,
                    mmbtu_override,
                    total_usd_override,
                    rupiah_override,
                    include_in_summary,
                    timestamp,
                ),
            )
        for region, target in normalized_targets.items():
            if target is None:
                con.execute(
                    "DELETE FROM monthly_average_price_targets WHERE month_start=%s AND region=%s",
                    (month_start.isoformat(), region),
                )
                continue
            con.execute(
                "INSERT INTO monthly_average_price_targets(month_start,region,target_price_rp_sm3,updated_at) "
                "VALUES(%s,%s,%s,%s) ON DUPLICATE KEY UPDATE "
                "target_price_rp_sm3=VALUES(target_price_rp_sm3),updated_at=VALUES(updated_at)",
                (month_start.isoformat(), region, target, timestamp),
            )
    return {"ok": True, "saved": len(normalized_entries)}


@app.post("/api/weekly-average-price")
async def save_weekly_average_price(request: Request):
    require_admin(request)
    payload = await request.json()
    customer_key = str(payload.get("customer_key", "")).strip()
    region = str(payload.get("region", "")).strip()
    try:
        week_start = date.fromisoformat(str(payload.get("week_start", "")))
        volume_mmbtu = float(payload.get("volume_mmbtu") or 0)
        price = float(payload.get("price_usd_per_sm3") or 0)
        exchange_rate = float(payload.get("exchange_rate") or 0)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Tanggal dan angka input harus valid.") from exc
    if week_start.weekday() != 0:
        raise HTTPException(status_code=400, detail="Tanggal minggu harus hari Senin.")
    if not customer_key or not region or volume_mmbtu < 0 or price < 0 or exchange_rate < 0:
        raise HTTPException(status_code=400, detail="Customer, wilayah, dan angka non-negatif wajib diisi.")
    if price > 0 and exchange_rate <= 0:
        raise HTTPException(status_code=400, detail="Kurs Rupiah per USD wajib lebih dari nol.")
    with db() as con:
        customer = con.execute("SELECT customer_key FROM customers WHERE customer_key=%s", (customer_key,)).fetchone()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer belum terdaftar.")
        con.execute(
            "INSERT INTO weekly_average_price_inputs(week_start,customer_key,region,volume_mmbtu,price_usd_per_sm3,exchange_rate,updated_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE region=VALUES(region),volume_mmbtu=VALUES(volume_mmbtu), "
            "price_usd_per_sm3=VALUES(price_usd_per_sm3),exchange_rate=VALUES(exchange_rate),updated_at=VALUES(updated_at)",
            (week_start.isoformat(), customer_key, region, volume_mmbtu, price, exchange_rate, datetime.now().isoformat(timespec="seconds")),
        )
    return {"ok": True}


@app.delete("/api/weekly-average-price")
def delete_weekly_average_price(request: Request, week_start: str, customer_key: str):
    require_admin(request)
    try:
        parsed_week = date.fromisoformat(week_start)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Format tanggal harus YYYY-MM-DD.") from exc
    with db() as con:
        con.execute("DELETE FROM weekly_average_price_inputs WHERE week_start=%s AND customer_key=%s", (parsed_week.isoformat(), customer_key))
    return {"ok": True}


@app.get("/api/import-history")
def import_history(request: Request):
    require_login(request)
    with db() as con:
        rows = con.execute("SELECT filename,imported_at,rows_read,rows_saved,status,message FROM import_history ORDER BY id DESC LIMIT 10").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/customer-mapping")
async def save_mapping(request: Request):
    require_admin(request)
    payload = await request.json()
    customer = str(payload.get("customer", "")).strip()
    operator = str(payload.get("operator", "")).strip().upper()
    customer_key, customer, operator = normalize_customer_mapping(customer, operator)
    with db() as con:
        existing = con.execute(
            "SELECT customer_key,operator FROM customers WHERE customer_key=%s",
            (customer_key,),
        ).fetchone()
        if existing and existing["operator"] != operator:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Key customer ini sudah terdaftar dengan operator berbeda. "
                    "Pilih customer yang sudah ada atau hubungi admin untuk pemetaan."
                ),
            )
        if not existing:
            con.execute(
                "INSERT INTO customers(customer_key,customer_name,operator) "
                "VALUES(%s,%s,%s)",
                (customer_key, customer, operator),
            )
    return {"ok": True, "customer_key": customer_key, "created": not bool(existing)}


@app.post("/api/customer-mapping/bulk")
async def save_customer_mappings(request: Request):
    require_admin(request)
    payload = await request.json()
    mappings = payload.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        raise HTTPException(status_code=400, detail="Pilih minimal satu pemetaan customer.")

    normalized_mappings = []
    for mapping in mappings:
        normalized_mappings.append(
            normalize_customer_mapping(mapping.get("customer"), mapping.get("operator"))
        )

    with db() as con:
        for customer_key, customer, operator in normalized_mappings:
            con.execute(
                "INSERT INTO customers(customer_key,customer_name,operator) VALUES(%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE customer_name=VALUES(customer_name),operator=VALUES(operator)",
                (customer_key, customer, operator),
            )
    return {"ok": True, "saved": len(normalized_mappings)}


@app.get("/api/customers")
def customers(request: Request):
    require_login(request)
    with db() as con:
        rows = con.execute(
            "SELECT customer_key,customer_name,operator FROM customers "
            "ORDER BY operator,customer_name"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/", include_in_schema=False)
@app.get("/{path:path}", include_in_schema=False)
def frontend_app():
    index_file = FRONTEND_DIST / "index.html"
    if not index_file.is_file():
        raise HTTPException(
            status_code=503,
            detail="React belum dibuild. Jalankan npm install dan npm run build di folder frontend.",
        )
    return FileResponse(index_file, headers={"Cache-Control": "no-cache, must-revalidate"})
