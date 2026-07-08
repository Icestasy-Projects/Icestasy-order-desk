import io
from datetime import datetime, timezone

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


def _format_date(created_at: str) -> str:
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%d %b %Y")
    except (ValueError, AttributeError):
        return created_at or ""


def build_orders_workbook(orders: list, role_label: str, full_name: str) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "Orders"

    last_col_letter = get_column_letter(len(COLUMNS))

    ws.merge_cells(f"A1:{last_col_letter}1")
    ws["A1"] = "Icestasy Order Desk — Orders Report"
    ws["A1"].font = TITLE_FONT

    ws.merge_cells(f"A2:{last_col_letter}2")
    generated = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    ws["A2"] = f"{full_name} · {role_label} · Generated {generated} · {len(orders)} orders"
    ws["A2"].font = SUBTLE_FONT

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

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
