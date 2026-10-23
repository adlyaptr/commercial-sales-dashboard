import os
import re
import hmac
import hashlib
import math
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote, urlsplit

import pymysql
from dotenv import load_dotenv
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pymysql.cursors import DictCursor
from starlette.middleware.sessions import SessionMiddleware
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

try:
    from .db import initialize_database
except ImportError:
    from db import initialize_database
    
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR / "static" / "react"
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
CUSTOMER_ASSIGNMENTS = {*OPERATORS, "OFF"}
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
        role in {"admin", "division"}
        or (username == APP_USERNAME and role is None)
    )


def require_login(request: Request):
    if not logged_in(request):
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu.")
    role = request.session.get("role")
    if role != "admin" and not (
        role is None and request.session.get("username") == APP_USERNAME
    ):
        raise HTTPException(status_code=403, detail="Akses khusus admin.")


def require_home_access(request: Request):
    if not logged_in(request):
        return
    username = request.session["username"]
    role = request.session.get("role")
    if role == "admin" or (role is None and username == APP_USERNAME):
        return
    with db() as con:
        user = con.execute(
            "SELECT role FROM app_users WHERE username=%s", (username,)
        ).fetchone()
    if not user or user["role"] != "division":
        request.session.clear()
        raise HTTPException(status_code=401, detail="Akun tidak lagi aktif.")


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
    return norm(customer), customer, operator


@app.post("/api/login")
async def login(request: Request):
    payload = await request.json()
    username = str(payload.get("username", ""))
    password = str(payload.get("password", ""))
    with db() as con:
        row = con.execute(
            "SELECT password_hash,role FROM app_users WHERE username=%s",
            (username,),
        ).fetchone()
    if (
        not row
        or row["role"] not in {"admin", "division"}
        or not verify_user_password(password, row["password_hash"])
    ):
        return JSONResponse({"detail": "Username atau password salah."}, status_code=401)
    request.session.clear()
    request.session["username"] = username
    request.session["role"] = row["role"]
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    if not logged_in(request):
        raise HTTPException(status_code=401, detail="Silakan login terlebih dahulu.")
    username = request.session["username"]
    with db() as con:
        user = con.execute(
            "SELECT role FROM app_users WHERE username=%s", (username,)
        ).fetchone()
    if not user or user["role"] not in {"admin", "division"}:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Akun tidak lagi aktif.")
    request.session["role"] = user["role"]
    return {"username": username, "role": user["role"]}


@app.get("/api/users")
def list_users(request: Request):
    require_login(request)
    with db() as con:
        users = con.execute(
            "SELECT username,role FROM app_users ORDER BY role,username"
        ).fetchall()
    return users


@app.post("/api/users")
async def create_user(request: Request):
    require_login(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format akun tidak valid.")
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,63}", username):
        raise HTTPException(
            status_code=400,
            detail="Username harus 3-64 karakter dan hanya boleh berisi huruf, angka, titik, garis bawah, atau tanda hubung.",
        )
    if len(password) < 12 or len(password) > 256:
        raise HTTPException(
            status_code=400,
            detail="Password akun divisi harus terdiri dari 12-256 karakter.",
        )
    with db() as con:
        existing = con.execute(
            "SELECT username FROM app_users WHERE username=%s", (username,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Username sudah digunakan.")
        con.execute(
            "INSERT INTO app_users(username,password_hash,role) VALUES(%s,%s,'division')",
            (username, hash_user_password(password)),
        )
    return {"username": username, "role": "division"}


@app.put("/api/users/{username}/password")
async def update_user_password(username: str, request: Request):
    require_login(request)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Format password tidak valid.")
    password = str(payload.get("password", ""))
    if len(password) < 12 or len(password) > 256:
        raise HTTPException(
            status_code=400,
            detail="Password akun divisi harus terdiri dari 12-256 karakter.",
        )
    with db() as con:
        user = con.execute(
            "SELECT role FROM app_users WHERE username=%s", (username,)
        ).fetchone()
        if not user or user["role"] != "division":
            raise HTTPException(status_code=404, detail="Akun divisi tidak ditemukan.")
        con.execute(
            "UPDATE app_users SET password_hash=%s WHERE username=%s",
            (hash_user_password(password), username),
        )
    return {"username": username, "role": "division"}


@app.delete("/api/users/{username}")
def delete_user(username: str, request: Request):
    require_login(request)
    if username == APP_USERNAME:
        raise HTTPException(status_code=400, detail="Akun admin utama tidak dapat dihapus.")
    with db() as con:
        user = con.execute(
            "SELECT role FROM app_users WHERE username=%s", (username,)
        ).fetchone()
        if not user or user["role"] != "division":
            raise HTTPException(status_code=404, detail="Akun divisi tidak ditemukan.")
        con.execute("DELETE FROM app_users WHERE username=%s", (username,))
    return {"ok": True}


@app.post("/api/import/preview")
async def preview_import(request: Request, file: UploadFile = File(...)):
    require_login(request)
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
    require_login(request)
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
    require_login(request)
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
    require_login(request)
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
    require_login(request)
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
            SELECT s.report_date, c.operator, s.customer_key, s.so, s.actual
            FROM sales s
            JOIN customers c ON c.customer_key = s.customer_key
            WHERE s.report_date BETWEEN %s AND %s
            ORDER BY s.report_date, c.operator, c.customer_key
            """,
            (year_start.isoformat(), month_end.isoformat()),
        ).fetchall()
        manual_so_row = con.execute(
            "SELECT so FROM monthly_so_targets WHERE month_start=%s",
            (month_start.isoformat(),),
        ).fetchone()

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
    if last_month.month == 12:
        after_last_month = date(last_month.year + 1, 1, 1)
    else:
        after_last_month = date(last_month.year, last_month.month + 1, 1)
    with db() as con:
        rows = con.execute(
            """
            SELECT s.report_date,c.operator,s.customer_key,s.so,s.actual
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
        report_totals = con.execute(
            "SELECT SUM(so) AS total_so,SUM(actual) AS total_actual FROM sales "
            "WHERE report_date >= %s AND report_date < %s",
            (first_month.isoformat(), after_last_month.isoformat()),
        ).fetchone()

    monthly_targets = {
        str(row["month_start"])[:7]: float(row["so"] or 0)
        for row in target_rows
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
            "so": float(report_totals["total_so"] or 0),
            "actual": float(report_totals["total_actual"] or 0),
        },
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
    require_login(request)
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
    previous_status=None,
    previous_status_changed_at=None,
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
        if previous_status == "Closed" and previous_status_changed_at:
            status_changed_at = (
                previous_status_changed_at.isoformat(timespec="seconds")
                if isinstance(previous_status_changed_at, datetime)
                else str(previous_status_changed_at)
            )
        else:
            status_changed_at = updated_at
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
    is_admin = request.session.get("role") == "admin" or (
        request.session.get("role") is None
        and request.session.get("username") == APP_USERNAME
    )
    if not is_admin:
        with db() as con:
            rows = con.execute(
                "SELECT report_date,status FROM complaints "
                "ORDER BY report_date DESC,id DESC"
            ).fetchall()
        return [
            {
                "date": row["report_date"].isoformat()
                if isinstance(row["report_date"], date)
                else str(row["report_date"]),
                "status": row["status"],
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
    require_login(request)
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
    require_login(request)
    if complaint_id < 1:
        raise HTTPException(status_code=400, detail="ID complain tidak valid.")
    with db() as con:
        current = con.execute(
            "SELECT status,status_changed_at FROM complaints WHERE id=%s",
            (complaint_id,),
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="Complain tidak ditemukan.")
        fields = normalize_complaint(
            await request.json(),
            previous_status=current["status"],
            previous_status_changed_at=current["status_changed_at"],
        )
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
    require_login(request)
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
        rows = con.execute(
            """
            SELECT
                c.customer_key,
                c.customer_name,
                c.operator,
                DATE_FORMAT(s.report_date, '%%Y-%%m') AS period,
                SUM(s.so) AS total_so,
                SUM(s.actual) AS total_actual
            FROM sales s
            JOIN customers c ON c.customer_key = s.customer_key
            WHERE s.report_date BETWEEN %s AND %s
            GROUP BY c.customer_key, c.customer_name, c.operator, period
            ORDER BY period, c.operator, c.customer_name
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchall()

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "items": [
            {
                "customer_key": row["customer_key"],
                "customer": row["customer_name"],
                "operator": row["operator"],
                "period": row["period"],
                "so": float(row["total_so"] or 0),
                "actual": float(row["total_actual"] or 0),
            }
            for row in rows
        ],
    }


def build_monthly_export(year, month, sales_rows, monthly_target):
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
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

    workbook = build_monthly_export(
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
            SELECT c.customer_name, c.operator, s.so, s.actual, s.id,
                   s.id, c.customer_key,
                   c.customer_key LIKE 'manualfob-%%' AS manual_fob
            FROM sales s JOIN customers c ON c.customer_key=s.customer_key
            WHERE s.report_date=%s ORDER BY c.operator, c.customer_name
        """, (report_date,)).fetchall()
        operator_data = {op: [] for op in (*OPERATORS, "OFF")}
        operator_totals = {
            op: {"so": 0.0, "actual": 0.0, "diff": 0.0, "customers": 0}
            for op in (*OPERATORS, "OFF")
        }
        for r in rows:
            customer_row = {
                "customer": r["customer_name"], "so": r["so"], "actual": r["actual"],
                "manual_fob": bool(r.get("manual_fob", False)),
                "diff": r["actual"] - r["so"]
            }
            if customer_row["manual_fob"]:
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
        rupiah = total_usd * exchange_rate
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
):
    if price_unit == "IDR_SM3":
        return price_rp > 0
    has_workbook_totals = all(
        value is not None
        for value in (mmbtu_override, total_usd_override, rupiah_override)
    )
    return price_usd > 0 and (
        (factor > 0 and exchange_rate > 0) or has_workbook_totals
    )


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
    exchange_rate = float(exchange["exchange_rate"] or 0) if exchange else 0.0

    rows = []
    totals = {"sm3": 0.0, "mmbtu": 0.0, "usd": 0.0, "rupiah": 0.0}
    for row in sales_rows:
        so_sm3 = float(row["so_sm3"] or 0)
        actual_sm3 = float(row["actual_sm3"] or 0)
        sm3 = (
            float(row["sm3_override"])
            if row.get("sm3_override") is not None
            else actual_sm3
        )
        factor = float(row["sm3_per_mmbtu"] or 0)
        price_unit = row.get("price_unit") or "USD_MMBTU"
        price = float(row["price_usd_per_mmbtu"] or 0)
        price_rp = float(row.get("price_rp_per_sm3") or 0)
        is_valid_price = has_valid_average_price(
            price_unit,
            price,
            price_rp,
            factor,
            exchange_rate,
            row.get("mmbtu_override"),
            row.get("total_usd_override"),
            row.get("rupiah_override"),
        )
        mmbtu, total_usd, rupiah = calculate_average_price(
            sm3,
            factor,
            price_unit,
            price,
            price_rp,
            exchange_rate,
            row.get("mmbtu_override"),
            row.get("total_usd_override"),
            row.get("rupiah_override"),
        )
        include_in_summary = bool(row.get("include_in_summary", True))
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
            "sm3_override": row.get("sm3_override"),
            "mmbtu_override": row.get("mmbtu_override"),
            "total_usd_override": row.get("total_usd_override"),
            "rupiah_override": row.get("rupiah_override"),
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
                   price_inputs.sm3_override,price_inputs.mmbtu_override,
                   price_inputs.total_usd_override,price_inputs.rupiah_override,
                   price_inputs.include_in_summary,
                   COALESCE(operator_factors.sm3_per_mmbtu,0) AS sm3_per_mmbtu,
                   COALESCE(exchange_rates.exchange_rate,0) AS exchange_rate
            FROM monthly_average_price_inputs price_inputs
            JOIN customers c ON c.customer_key=price_inputs.customer_key
            LEFT JOIN monthly_average_price_operator_factors operator_factors
              ON operator_factors.month_start=price_inputs.month_start
             AND operator_factors.operator=c.operator
            LEFT JOIN monthly_average_price_exchange_rates exchange_rates
              ON exchange_rates.month_start=price_inputs.month_start
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
        (row["period"], row["customer_key"]): row for row in sales_rows
    }
    for row in input_rows:
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
        next_period_start = (
            date(period_start.year + 1, 1, 1)
            if period_start.month == 12
            else date(period_start.year, period_start.month + 1, 1)
        )
        is_full_month = (
            start <= period_start
            and end >= next_period_start - timedelta(days=1)
        )
        sm3_override = row.get("sm3_override") if is_full_month else None
        mmbtu_override = row.get("mmbtu_override") if is_full_month else None
        total_usd_override = row.get("total_usd_override") if is_full_month else None
        rupiah_override = row.get("rupiah_override") if is_full_month else None
        sm3 = float(sm3_override) if sm3_override is not None else actual_sm3
        factor = float(row["sm3_per_mmbtu"] or 0)
        price_unit = row.get("price_unit") or "USD_MMBTU"
        price = float(row["price_usd_per_mmbtu"] or 0)
        price_rp = float(row.get("price_rp_per_sm3") or 0)
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
        )
        include_in_summary = bool(row.get("include_in_summary", True))
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
            "sm3_override": row.get("sm3_override"),
            "mmbtu_override": row.get("mmbtu_override"),
            "total_usd_override": row.get("total_usd_override"),
            "rupiah_override": row.get("rupiah_override"),
            "total_usd": total_usd,
            "exchange_rate": exchange_rate,
            "has_valid_price": is_valid_price,
            "include_in_summary": include_in_summary,
            "rupiah": rupiah,
        })
    totals["average_price_rp_sm3"] = (
        totals["rupiah"] / totals["sm3"] if totals["sm3"] else 0.0
    )
    if not logged_in(request):
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
    require_login(request)
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
        for entry in entries:
            customer_key = str(entry.get("customer_key", "")).strip()
            region = str(entry.get("region", "")).strip()
            price_unit = str(entry.get("price_unit") or "USD_MMBTU").strip()
            if price_unit == "IDR_SM3":
                price_usd = 0.0
                price_rp = float(entry.get("price_rp_per_sm3") or 0)
            elif price_unit == "USD_MMBTU":
                price_usd = float(entry.get("price_usd_per_mmbtu") or 0)
                price_rp = 0.0
            else:
                raise ValueError
            if (
                not customer_key
                or not math.isfinite(price_usd)
                or price_usd < 0
                or not math.isfinite(price_rp)
                or price_rp < 0
            ):
                raise ValueError
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
            normalized_targets[region] = target_value
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
            sm3_override,
            mmbtu_override,
            total_usd_override,
            rupiah_override,
            include_in_summary,
        ) in normalized_entries:
            con.execute(
                "INSERT INTO monthly_average_price_inputs("
                "month_start,customer_key,region,price_unit,price_usd_per_mmbtu,"
                "price_rp_per_sm3,sm3_override,mmbtu_override,total_usd_override,"
                "rupiah_override,include_in_summary,updated_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE region=VALUES(region),price_unit=VALUES(price_unit),"
                "price_usd_per_mmbtu=VALUES(price_usd_per_mmbtu),"
                "price_rp_per_sm3=VALUES(price_rp_per_sm3),"
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
    require_login(request)
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
    require_login(request)
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
    require_login(request)
    payload = await request.json()
    customer = str(payload.get("customer", "")).strip()
    operator = str(payload.get("operator", "")).strip().upper()
    customer_key, customer, operator = normalize_customer_mapping(customer, operator)
    with db() as con:
        con.execute("INSERT INTO customers(customer_key,customer_name,operator) VALUES(%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE customer_name=VALUES(customer_name),operator=VALUES(operator)",
                    (customer_key, customer, operator))
    return {"ok": True}


@app.post("/api/customer-mapping/bulk")
async def save_customer_mappings(request: Request):
    require_login(request)
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
    return FileResponse(index_file)
