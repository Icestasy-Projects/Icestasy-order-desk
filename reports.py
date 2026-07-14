import io
from datetime import date, datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

BRAND_FILL = PatternFill(start_color="FF8A3D", end_color="FF8A3D", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(bold=True, size=14, color="21201D")
SUBTLE_FONT = Font(size=10, color="847E74", italic=True)
TOTAL_FONT = Font(bold=True)

STATUS_LABELS = {
    "draft": "Order Pending", "pending_approval": "In Progress", "approved": "In Progress",
    "in_production": "In Progress", "dispatched": "In Progress", "delivered": "Completed",
    "rejected": "Rejected", "cancelled": "Cancelled", "invoiced": "Invoiced",
}
PAY_LABELS = {
    "received": "Payment Completed", "pending": "Payment Pending", "failed": "Payment Failed",
    "refunded": "Refunded", "not_recorded": "Not Recorded",
}

COLUMNS = ["Order No", "Date", "Client", "Locality", "City", "Salesperson", "Status", "Payment Status", "Amount (INR)"]
COLUMN_WIDTHS = [16, 14, 28, 20, 16, 18, 16, 18, 14]

# Mumbai Metropolitan Region: reported as a single "Mumbai" group, matching the dashboard's By City tab.
MMR_CITIES = {"Mumbai", "Vasai-Virar", "Thane", "Navi Mumbai"}

REPORT_TYPE_LABELS = {
    "all": "All Orders", "month": "Month on Month", "city": "City-wise",
    "client": "Client-wise", "salesperson": "Salesperson-wise",
}
GROUP_LABELS = {"month": "Month", "city": "City", "client": "Client", "salesperson": "Salesperson"}


def _format_date(created_at: str) -> str:
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%d %b %Y")
    except (ValueError, AttributeError):
        return created_at or ""


def _month_label(created_at: str) -> str:
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%B %Y")
    except (ValueError, AttributeError):
        return created_at or "—"


def _report_city(o: dict) -> str:
    city = o.get("city")
    return "Mumbai" if city in MMR_CITIES else (city or "—")


GROUP_KEY_FUNCS = {
    "month": lambda o: _month_label(o.get("created_at", "")),
    "city": _report_city,
    "client": lambda o: o.get("client_name") or "—",
    "salesperson": lambda o: o.get("salesperson_name") or "—",
}


def _last_12_months_range() -> tuple:
    today = date.today()
    month_index = today.year * 12 + (today.month - 1) - 11
    start = date(month_index // 12, month_index % 12 + 1, 1)
    return start.isoformat(), today.isoformat()


def _in_range(created_at: str, date_from: str, date_to: str) -> bool:
    try:
        d = datetime.fromisoformat((created_at or "").replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return True
    if date_from:
        try:
            if d < datetime.strptime(date_from, "%Y-%m-%d").date():
                return False
        except ValueError:
            pass
    if date_to:
        try:
            if d > datetime.strptime(date_to, "%Y-%m-%d").date():
                return False
        except ValueError:
            pass
    return True


def _sheet_header(ws, title_text: str, subtitle_text: str, last_col_letter: str):
    ws.merge_cells(f"A1:{last_col_letter}1")
    ws["A1"] = title_text
    ws["A1"].font = TITLE_FONT
    ws.merge_cells(f"A2:{last_col_letter}2")
    ws["A2"] = subtitle_text
    ws["A2"].font = SUBTLE_FONT


def _write_summary_sheet(ws, orders: list, report_type: str, subtitle_text: str):
    group_func = GROUP_KEY_FUNCS[report_type]
    group_label = GROUP_LABELS[report_type]
    columns = [group_label, "Orders", "Total Value (INR)"]
    last_col_letter = get_column_letter(len(columns))

    _sheet_header(ws, f"Icestasy Order Desk — {REPORT_TYPE_LABELS[report_type]} Report", subtitle_text, last_col_letter)

    header_row = 4
    for col, title in enumerate(columns, start=1):
        cell = ws.cell(row=header_row, column=col, value=title)
        cell.font = HEADER_FONT
        cell.fill = BRAND_FILL
        cell.alignment = Alignment(horizontal="center")

    totals = {}
    for o in orders:
        key = group_func(o) or "—"
        entry = totals.setdefault(key, {"count": 0, "value": 0.0})
        entry["count"] += 1
        entry["value"] += o.get("total_amount", 0) or 0

    row = header_row + 1
    grand_total = 0.0
    for name, entry in sorted(totals.items(), key=lambda kv: kv[1]["value"], reverse=True):
        ws.cell(row=row, column=1, value=name)
        ws.cell(row=row, column=2, value=entry["count"])
        amount_cell = ws.cell(row=row, column=3, value=entry["value"])
        amount_cell.number_format = "#,##0.00"
        grand_total += entry["value"]
        row += 1

    ws.cell(row=row, column=1, value="Total").font = TOTAL_FONT
    total_cell = ws.cell(row=row, column=3, value=grand_total)
    total_cell.font = TOTAL_FONT
    total_cell.number_format = "#,##0.00"

    for i, width in enumerate([28, 12, 20], start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = f"A{header_row + 1}"
    ws.auto_filter.ref = f"A{header_row}:{last_col_letter}{header_row}"


def _write_orders_sheet(ws, orders: list, subtitle_text: str):
    last_col_letter = get_column_letter(len(COLUMNS))
    _sheet_header(ws, "Icestasy Order Desk — Orders Report", subtitle_text, last_col_letter)

    header_row = 4
    for col, title in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=header_row, column=col, value=title)
        cell.font = HEADER_FONT
        cell.fill = BRAND_FILL
        cell.alignment = Alignment(horizontal="center")

    amount_col = len(COLUMNS)
    row = header_row + 1
    total_value = 0.0
    for o in orders:
        values = [
            o.get("order_no"), _format_date(o.get("created_at", "")), o.get("client_name"),
            o.get("place"), o.get("city"), o.get("salesperson_name"),
            STATUS_LABELS.get(o.get("status"), o.get("status")),
            PAY_LABELS.get(o.get("payment_status"), o.get("payment_status")),
            o.get("total_amount", 0),
        ]
        for col, val in enumerate(values, start=1):
            cell = ws.cell(row=row, column=col, value=val)
            if col == amount_col:
                cell.number_format = "#,##0.00"
        total_value += o.get("total_amount", 0) or 0
        row += 1

    total_label_col = amount_col - 1
    ws.cell(row=row, column=total_label_col, value="Total").font = TOTAL_FONT
    total_cell = ws.cell(row=row, column=amount_col, value=total_value)
    total_cell.font = TOTAL_FONT
    total_cell.number_format = "#,##0.00"

    for i, width in enumerate(COLUMN_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    ws.freeze_panes = f"A{header_row + 1}"
    ws.auto_filter.ref = f"A{header_row}:{last_col_letter}{header_row}"


def build_orders_workbook(orders: list, role_label: str, full_name: str,
                           report_type: str = "all", date_from: str = None, date_to: str = None) -> io.BytesIO:
    if report_type not in REPORT_TYPE_LABELS:
        report_type = "all"
    if report_type == "month" and not date_from and not date_to:
        date_from, date_to = _last_12_months_range()
    if date_from or date_to:
        orders = [o for o in orders if _in_range(o.get("created_at", ""), date_from, date_to)]

    generated = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    range_text = f" · {date_from or '…'} to {date_to or '…'}" if (date_from or date_to) else ""
    subtitle_text = f"{full_name} · {role_label} · Generated {generated} · {len(orders)} orders{range_text}"

    wb = Workbook()
    if report_type == "all":
        ws = wb.active
        ws.title = "Orders"
        _write_orders_sheet(ws, orders, subtitle_text)
    else:
        summary_ws = wb.active
        summary_ws.title = "Summary"
        _write_summary_sheet(summary_ws, orders, report_type, subtitle_text)
        detail_ws = wb.create_sheet("Orders")
        _write_orders_sheet(detail_ws, orders, subtitle_text)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
