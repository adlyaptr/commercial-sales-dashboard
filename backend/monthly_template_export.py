import calendar
from copy import copy
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
import re

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.cell.cell import MergedCell


TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "monthly_sales_template.xlsx"
OPERATORS = ("SETU", "KHT", "BLORA", "WUNUT")
MONTH_NAMES = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
TOTAL_HEADER_MARKERS = ("TOTAL", "DATA ")


def _normalize(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _customer_header(sheet, header_row, customer):
    customer_key = _normalize(customer)
    if not customer_key:
        return None

    candidates = []
    for column in range(7, sheet.max_column + 1):
        label = sheet.cell(header_row, column).value
        if not label:
            continue
        label_text = " ".join(str(label).split()).strip()
        if any(marker in label_text.upper() for marker in TOTAL_HEADER_MARKERS):
            continue
        if str(sheet.cell(header_row + 1, column).value or "").strip().upper() != "SO":
            continue
        if str(sheet.cell(header_row + 1, column + 1).value or "").strip().upper() != "ACTUAL":
            continue
        header_key = _normalize(label_text)
        candidates.append((header_key, column))

    for header_key, column in candidates:
        if customer_key == header_key:
            return column

    customer_alias = re.sub(r"^(cv|pt|persero)", "", customer_key)
    for header_key, column in candidates:
        if customer_alias == header_key:
            return column
        if header_key.startswith("fob") and customer_key.startswith(header_key):
            return column
        if customer_key.startswith(header_key) and len(header_key) >= 5:
            return column
    return None


def _style_row(sheet, target_row, source_row, last_column):
    for column in range(1, last_column + 1):
        source = sheet.cell(source_row, column)
        target = sheet.cell(target_row, column)
        if not isinstance(target, MergedCell):
            target._style = copy(source._style)
            if source.has_style:
                target.number_format = source.number_format
    if source_row in sheet.row_dimensions:
        sheet.row_dimensions[target_row].height = sheet.row_dimensions[source_row].height


def _set_row_values(sheet, row, values):
    for column, value in values.items():
        cell = sheet.cell(row, column)
        if not isinstance(cell, MergedCell):
            cell.value = value


def _clear_cell(sheet, row, column):
    cell = sheet.cell(row, column)
    if not isinstance(cell, MergedCell):
        cell.value = None


def _prepare_operator_sheet(sheet, operator, year, month, sales_by_day):
    is_wunut = operator == "WUNUT"
    header_row = 7 if is_wunut else 12
    first_data_row = header_row + 2
    grand_total_row = next(
        row
        for row in range(first_data_row, sheet.max_row + 1)
        if str(sheet.cell(row, 2).value or "").strip().casefold() == "total"
    )
    last_column = sheet.max_column
    template_day_row = next(
        row for row in range(first_data_row, grand_total_row)
        if isinstance(sheet.cell(row, 4).value, str)
        and sheet.cell(row, 4).value.startswith("=SUMIF")
    )
    template_subtotal_row = next(
        row for row in range(first_data_row, grand_total_row)
        if str(sheet.cell(row, 2).value or "").strip().casefold().startswith("sub total")
    )
    template_blank_row = next(
        (
            row for row in range(template_subtotal_row + 1, grand_total_row)
            if all(sheet.cell(row, column).value is None for column in range(1, 7))
        ),
        template_day_row,
    )

    week_merges = [
        merged for merged in list(sheet.merged_cells.ranges)
        if merged.min_col == merged.max_col == 1
        and first_data_row <= merged.min_row < grand_total_row
    ]
    for merged in week_merges:
        sheet.unmerge_cells(str(merged))

    customer_columns = {}
    unmapped_rows = {}
    for report_day, rows in sales_by_day.items():
        for row in rows:
            if row["operator"] != operator:
                continue
            column = _customer_header(sheet, header_row, row["customer"])
            if column is None:
                key = _normalize(row["customer"])
                if key not in unmapped_rows:
                    unmapped_rows[key] = (row["customer"], last_column + 1 + len(unmapped_rows) * 3)
                column = unmapped_rows[key][1]
            totals = customer_columns.setdefault(
                (report_day, column),
                {"so": 0.0, "actual": 0.0},
            )
            totals["so"] += row["so"]
            totals["actual"] += row["actual"]

    # Keep unknown customer names in additional template-style SO/Actual/Diff columns.
    for customer, column in unmapped_rows.values():
        for offset in range(3):
            target_column = column + offset
            source_column = 7 + offset
            sheet.column_dimensions[get_column_letter(target_column)].width = (
                sheet.column_dimensions[get_column_letter(source_column)].width
            )
            for row in range(header_row, grand_total_row + 1):
                source = sheet.cell(row, source_column)
                target = sheet.cell(row, target_column)
                target._style = copy(source._style)
        sheet.merge_cells(
            start_row=header_row,
            start_column=column,
            end_row=header_row,
            end_column=column + 2,
        )
        sheet.cell(header_row, column).value = customer
        for offset, label in enumerate(("SO", "Actual", "Diff Actual - SO")):
            sheet.cell(header_row + 1, column + offset).value = label
        last_column = max(last_column, column + 2)

    month_days = [
        date(year, month, day)
        for day in range(1, calendar.monthrange(year, month)[1] + 1)
    ]
    week_groups = {}
    for report_day in month_days:
        week_start = report_day - timedelta(days=report_day.weekday())
        week_groups.setdefault(week_start, []).append(report_day)
    week_groups = list(week_groups.values())

    for merged in list(sheet.merged_cells.ranges):
        if merged.min_row < grand_total_row and merged.max_row >= first_data_row:
            if merged.min_col == 1 and merged.max_col == 1:
                sheet.unmerge_cells(str(merged))

    row_cursor = first_data_row
    customer_totals = {}
    operator_so = 0.0
    operator_actual = 0.0
    for week_number, week in enumerate(week_groups, start=1):
        week_so = 0.0
        week_actual = 0.0
        week_customer_totals = {}
        week_start_row = row_cursor
        for report_day in week:
            _style_row(sheet, row_cursor, template_day_row, last_column)
            for column in range(1, last_column + 1):
                _clear_cell(sheet, row_cursor, column)
            day_rows = sales_by_day.get(report_day, [])
            day_so = sum(row["so"] for row in day_rows if row["operator"] == operator)
            day_actual = sum(row["actual"] for row in day_rows if row["operator"] == operator)
            values = {
                2: report_day,
                3: DAY_NAMES[report_day.weekday()],
                4: day_so,
                5: day_actual,
                6: day_actual - day_so,
            }
            day_customer_totals = {
                column: amount
                for (day, column), amount in customer_columns.items()
                if day == report_day
            }
            for column, amount in day_customer_totals.items():
                values[column] = amount["so"]
                values[column + 1] = amount["actual"]
                values[column + 2] = amount["actual"] - amount["so"]
                aggregate = week_customer_totals.setdefault(
                    column, {"so": 0.0, "actual": 0.0}
                )
                aggregate["so"] += amount["so"]
                aggregate["actual"] += amount["actual"]
                month_aggregate = customer_totals.setdefault(
                    column, {"so": 0.0, "actual": 0.0}
                )
                month_aggregate["so"] += amount["so"]
                month_aggregate["actual"] += amount["actual"]
            _set_row_values(sheet, row_cursor, values)
            week_so += day_so
            week_actual += day_actual
            operator_so += day_so
            operator_actual += day_actual
            row_cursor += 1

        _style_row(sheet, row_cursor, template_subtotal_row, last_column)
        for column in range(1, last_column + 1):
            _clear_cell(sheet, row_cursor, column)
        subtotal_values = {
            2: f"Sub Total Week {week_number}",
            4: week_so,
            5: week_actual,
            6: week_actual - week_so,
        }
        for column, amount in week_customer_totals.items():
            subtotal_values[column] = amount["so"]
            subtotal_values[column + 1] = amount["actual"]
            subtotal_values[column + 2] = amount["actual"] - amount["so"]
        _set_row_values(sheet, row_cursor, subtotal_values)
        subtotal_row = row_cursor
        row_cursor += 1
        if week_number < len(week_groups):
            _style_row(sheet, row_cursor, template_blank_row, last_column)
            for column in range(1, last_column + 1):
                _clear_cell(sheet, row_cursor, column)
            row_cursor += 1
        sheet.merge_cells(
            start_row=week_start_row,
            start_column=1,
            end_row=subtotal_row,
            end_column=1,
        )
        sheet.cell(week_start_row, 1).value = week_number

    if row_cursor > grand_total_row:
        raise ValueError(f"Template sheet {operator} tidak memiliki ruang untuk data bulan ini.")

    for row in range(row_cursor, grand_total_row):
        for column in range(1, last_column + 1):
            _clear_cell(sheet, row, column)
    for column in range(1, last_column + 1):
        _clear_cell(sheet, grand_total_row, column)
    _set_row_values(
        sheet,
        grand_total_row,
        {
            2: "Total",
            4: operator_so,
            5: operator_actual,
            6: operator_actual - operator_so,
        },
    )
    for column, amount in customer_totals.items():
        _set_row_values(
            sheet,
            grand_total_row,
            {
                column: amount["so"],
                column + 1: amount["actual"],
                column + 2: amount["actual"] - amount["so"],
            },
        )

    anchor_cell = "A5" if is_wunut else "A10"
    sheet[anchor_cell] = date(year, month, 1)
    if is_wunut:
        sheet["A3"] = None
    for row in range(grand_total_row + 1, sheet.max_row + 1):
        for column in range(1, sheet.max_column + 1):
            _clear_cell(sheet, row, column)


def _write_summary(sheet, month, sales_by_day, monthly_target):
    month_column = month + 2
    summary_rows = range(6, sheet.max_row + 1)
    for row in summary_rows:
        for column in range(3, sheet.max_column + 1):
            _clear_cell(sheet, row, column)

    totals = {
        operator: {"so": 0.0, "actual": 0.0, "fob_so": 0.0, "fob_actual": 0.0}
        for operator in (*OPERATORS, "OFF")
    }
    for rows in sales_by_day.values():
        for row in rows:
            operator_total = totals.setdefault(
                row["operator"],
                {"so": 0.0, "actual": 0.0, "fob_so": 0.0, "fob_actual": 0.0},
            )
            operator_total["so"] += row["so"]
            operator_total["actual"] += row["actual"]
            if "fob" in _normalize(row["customer"]):
                operator_total["fob_so"] += row["so"]
                operator_total["fob_actual"] += row["actual"]

    total_so = sum(item["so"] for item in totals.values())
    total_actual = sum(item["actual"] for item in totals.values())
    fob_so = sum(item["fob_so"] for item in totals.values())
    fob_actual = sum(item["fob_actual"] for item in totals.values())
    target = float(monthly_target) if monthly_target is not None else total_so
    values = {
        6: target,
        7: target - fob_so,
        8: fob_so,
        12: total_actual,
        13: total_actual - fob_actual,
        14: fob_actual,
        17: total_actual - target,
        18: (total_actual - fob_actual) - (target - fob_so),
        19: fob_actual - fob_so,
    }

    def operator_values(operator):
        item = totals[operator]
        return item["so"] - item["fob_so"], item["fob_so"], item["actual"] - item["fob_actual"], item["fob_actual"]

    kht_so, kht_fob_so, kht_actual, kht_fob_actual = operator_values("KHT")
    setu_so, setu_fob_so, setu_actual, setu_fob_actual = operator_values("SETU")
    blora_so, blora_fob_so, blora_actual, blora_fob_actual = operator_values("BLORA")
    wunut_so, wunut_fob_so, wunut_actual, wunut_fob_actual = operator_values("WUNUT")
    _, off_fob_so, off_actual, off_fob_actual = operator_values("OFF")
    values.update({
        27: target,
        28: 0,
        32: kht_actual + setu_actual,
        33: kht_fob_actual + setu_fob_actual,
        42: kht_so,
        43: kht_fob_so,
        44: kht_so + kht_fob_so,
        45: setu_so,
        46: setu_fob_so,
        47: setu_so + setu_fob_so,
        50: kht_actual,
        51: kht_fob_actual,
        52: kht_actual + kht_fob_actual,
        54: setu_actual,
        55: setu_fob_actual,
        56: setu_actual + setu_fob_actual,
        57: off_actual,
        58: off_fob_actual,
        59: off_actual + off_fob_actual,
        77: blora_actual + wunut_actual,
        78: blora_fob_actual + wunut_fob_actual,
        88: blora_so,
        89: blora_fob_so,
        90: blora_so + blora_fob_so,
        91: wunut_so,
        92: wunut_fob_so,
        93: wunut_so + wunut_fob_so,
        96: blora_actual,
        97: blora_fob_actual,
        98: blora_actual + blora_fob_actual,
        99: wunut_actual,
        100: wunut_fob_actual,
        101: wunut_actual + wunut_fob_actual,
        37: kht_actual + setu_actual - kht_so - setu_so,
        38: kht_fob_actual + setu_fob_actual - kht_fob_so - setu_fob_so,
        62: kht_actual - kht_so,
        63: kht_fob_actual - kht_fob_so,
        64: kht_actual + kht_fob_actual - kht_so - kht_fob_so,
        65: setu_actual - setu_so,
        66: setu_fob_actual - setu_fob_so,
        67: setu_actual + setu_fob_actual - setu_so - setu_fob_so,
        83: blora_actual + wunut_actual - blora_so - wunut_so,
        84: blora_fob_actual + wunut_fob_actual - blora_fob_so - wunut_fob_so,
        104: blora_actual - blora_so,
        105: blora_fob_actual - blora_fob_so,
        106: blora_actual + blora_fob_actual - blora_so - blora_fob_so,
        107: wunut_actual - wunut_so,
        108: wunut_fob_actual - wunut_fob_so,
        109: wunut_actual + wunut_fob_actual - wunut_so - wunut_fob_so,
    })
    for row, value in values.items():
        sheet.cell(row, month_column).value = value
        sheet.cell(row, 15).value = value


def _write_weekly_summary(sheet, year, month, sales_by_day, monthly_target):
    days_in_month = calendar.monthrange(year, month)[1]
    all_sales = [
        row
        for rows in sales_by_day.values()
        for row in rows
    ]
    total_so = sum(row["so"] for row in all_sales)
    total_actual = sum(row["actual"] for row in all_sales)
    target = float(monthly_target) if monthly_target is not None else total_so
    daily_target = target / days_in_month
    month_names = MONTH_NAMES
    sheet["C1"] = f"RKAP {month_names[month - 1]} {year}"

    week_groups = {}
    for day_number in range(1, days_in_month + 1):
        report_day = date(year, month, day_number)
        week_start = report_day - timedelta(days=report_day.weekday())
        week_groups.setdefault(week_start, []).append(report_day)
    week_groups = list(week_groups.values())
    calendar_week_count = len(week_groups)
    if len(week_groups) > 5:
        week_groups = [*week_groups[:4], [day for group in week_groups[4:] for day in group]]

    for row in range(3, 10):
        for column in range(12, sheet.max_column + 1):
            _clear_cell(sheet, row, column)
    for week in range(5):
        row_number = week + 3
        if week >= len(week_groups):
            for column in range(1, 12):
                _clear_cell(sheet, row_number, column)
            continue
        week_days = week_groups[week]
        week_so = sum(
            row["so"] for day in week_days for row in sales_by_day.get(day, [])
        )
        week_actual = sum(
            row["actual"] for day in week_days for row in sales_by_day.get(day, [])
        )
        week_target = daily_target * len(week_days)
        values = (
            (
                f"Sub Total Week {week + 1}"
                if calendar_week_count <= 5 or week < 4
                else f"Sub Total Week {week + 1}-{calendar_week_count}"
            ),
            week_target,
            week_so,
            week_actual,
            week_actual - week_so,
            week_actual - week_target,
            (week_actual - week_so) / week_so if week_so else 0,
            week_actual / week_target if week_target else 0,
            week_actual / week_so if week_so else 0,
            (week_actual - week_target) / week_target if week_target else 0,
        )
        _clear_cell(sheet, row_number, 1)
        sheet.cell(row_number, 1).value = values[0]
        for column, value in enumerate(values[1:], start=3):
            _clear_cell(sheet, row_number, column)
            sheet.cell(row_number, column).value = value

    _clear_cell(sheet, 8, 1)
    sheet.cell(8, 1).value = "TOTAL"
    for column, value in enumerate((
        target,
        total_so,
        total_actual,
        total_actual - total_so,
        total_actual - target,
        (total_actual - total_so) / total_so if total_so else 0,
        total_actual / target if target else 0,
        total_actual / total_so if total_so else 0,
        (total_actual - target) / target if target else 0,
    ), start=3):
        _clear_cell(sheet, 8, column)
        sheet.cell(8, column).value = value
    sheet["C9"] = daily_target
    sheet["A10"] = date(year, month, 1)

    range_end_rows = {"SETU": (52, 55), "KHT": (52, 55), "BLORA": (52, 55), "WUNUT": (47, 50)}
    for row in sheet.iter_rows():
        for cell in row:
            formula = cell.value
            if not isinstance(formula, str) or not formula.startswith("="):
                continue
            for operator, (original_last_row, last_row) in range_end_rows.items():
                pattern = (
                    rf"({operator}!\$?[A-Z]+\$?\d+:\$?[A-Z]+\$?)"
                    rf"{original_last_row}\b"
                )
                cell.value = re.sub(pattern, rf"\g<1>{last_row}", cell.value)

    for row in range(14, sheet.max_row + 1):
        for column in range(1, sheet.max_column + 1):
            cell = sheet.cell(row, column)
            if isinstance(cell.value, (int, float)):
                _clear_cell(sheet, row, column)


def build_monthly_template_export(year, month, sales_rows, monthly_target):
    if not TEMPLATE_PATH.is_file():
        raise FileNotFoundError(f"Template ekspor tidak ditemukan: {TEMPLATE_PATH}")
    workbook = load_workbook(TEMPLATE_PATH)
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    sales_by_day = {}
    for source_row in sales_rows:
        report_day = source_row["report_date"]
        if isinstance(report_day, str):
            report_day = date.fromisoformat(report_day)
        if not month_start <= report_day <= month_end:
            continue
        sale = {
            "customer": str(source_row["customer_name"]),
            "operator": str(source_row["operator"]).upper(),
            "so": float(source_row["so"] or 0),
            "actual": float(source_row["actual"] or 0),
        }
        sales_by_day.setdefault(report_day, []).append(sale)

    _write_summary(workbook["SUMMARY REPORT"], month, sales_by_day, monthly_target)
    _write_weekly_summary(workbook["Weekly Summary"], year, month, sales_by_day, monthly_target)
    for operator in OPERATORS:
        sheet = workbook[operator]
        _prepare_operator_sheet(sheet, operator, year, month, sales_by_day)

    workbook.calculation.fullCalcOnLoad = True
    workbook.calculation.forceFullCalc = True
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
