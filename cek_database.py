from pathlib import Path
from urllib.parse import urlsplit, unquote
from dotenv import load_dotenv
import os
import pymysql

load_dotenv(Path("backend") / ".env")
u = urlsplit(os.getenv("DATABASE_URL", ""))

conn = pymysql.connect(
    host=u.hostname,
    port=u.port or 3306,
    user=unquote(u.username or ""),
    password=unquote(u.password or ""),
    database=unquote(u.path.lstrip("/")),
    connect_timeout=5,
)

try:
    with conn.cursor() as cur:
        queries = {
            "JUMLAH CUSTOMER PER OPERATOR": """
                SELECT operator, COUNT(*)
                FROM customers
                GROUP BY operator
                ORDER BY operator
            """,
            "TOTAL BARIS SALES": """
                SELECT COUNT(*) FROM sales
            """,
            "INDEKS TABEL SALES": """
                SHOW INDEX FROM sales
            """,
            "MAPPING TIDAK VALID": """
                SELECT COUNT(*)
                FROM customers
                WHERE TRIM(customer_name) = ''
                   OR operator NOT IN ('SETU', 'KHT', 'BLORA', 'WUNUT')
            """,
        }

        for title, sql in queries.items():
            print(f"\n=== {title} ===")
            cur.execute(sql)
            for row in cur.fetchall():
                print(row)
finally:
    conn.close()