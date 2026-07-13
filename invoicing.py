"""Tax invoice PDF generation, matching Icestasy's real invoice format
(company block, consignee/buyer, HSN-coded line items, CGST/SGST or IGST
depending on interstate vs intrastate, running client balance, UPI QR)."""
import io
from datetime import datetime, timezone

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image

from order_engine import _sb

COMPANY = {
    "name": "Icestasy Projects Pvt. Ltd.",
    "address": "G-3, Platinum- The Residence,, Tejpal Scheme Road No.-05, "
               "Vile Parle (East), Mumbai-400057",
    "mobile": "+91 8050588847 / +91 9324590822",
    "fssai": "11519005000191",
    "msme": "UDYAM-MH-18-0108198 Micro",
    "gstin": "27AAECI1609N1ZE",
    "state": "Maharashtra",
    "state_code": "27",
    "godown": "Goregaon",
    "bank_name": "ICICI",
    "bank_account_no": "021105005270",
    "ifsc": "ICIC0000211",
    "branch": "Vile Parle Branch",
    "upi_id": "Icestasy@icici",
}

# ── Amount in words (Indian numbering: crore/lakh/thousand) ─────────────────
_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
         "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
         "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two_digit_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three_digit_words(n: int) -> str:
    if n >= 100:
        rest = n % 100
        return _ONES[n // 100] + " Hundred" + (" " + _two_digit_words(rest) if rest else "")
    return _two_digit_words(n)


def amount_in_words(amount: float) -> str:
    rupees = int(round(amount))
    if rupees == 0:
        return "INR Zero Only"
    parts = []
    crore, rupees = divmod(rupees, 10_000_000)
    lakh, rupees = divmod(rupees, 100_000)
    thousand, rupees = divmod(rupees, 1000)
    hundred = rupees
    if crore:
        parts.append(_three_digit_words(crore) + " Crore")
    if lakh:
        parts.append(_three_digit_words(lakh) + " Lakh")
    if thousand:
        parts.append(_three_digit_words(thousand) + " Thousand")
    if hundred:
        parts.append(_three_digit_words(hundred))
    return "INR " + " ".join(parts) + " Only"


# ── Client running balance (Dr/Cr ledger, not just this one order) ──────────

def _client_ledger(sb, client_id: int, as_of_iso: str) -> dict:
    orders = (
        sb.schema("sales").from_("orders")
        .select("id, status, total_amount, created_at")
        .eq("client_id", client_id).execute().data
    )
    total_invoiced = sum(
        float(o["total_amount"]) for o in orders
        if o["status"] == "invoiced" and o["created_at"] <= as_of_iso
    )
    order_ids = [o["id"] for o in orders]
    payments = []
    if order_ids:
        payments = (
            sb.schema("sales").from_("payments")
            .select("amount, received_at, order_id")
            .in_("order_id", order_ids).eq("status", "received")
            .lte("received_at", as_of_iso)
            .order("received_at", desc=True).execute().data
        )
    total_paid = sum(float(p["amount"]) for p in payments)
    last_payment = payments[0] if payments else None
    return {
        "balance": total_invoiced - total_paid,
        "last_payment_amount": float(last_payment["amount"]) if last_payment else None,
        "last_payment_date": last_payment["received_at"] if last_payment else None,
    }


def _addr_block(addr: dict | None) -> str:
    if not addr:
        return ""
    parts = [p for p in [addr.get("line1"), addr.get("line2")] if p]
    line1 = ", ".join(parts)
    city_state = ", ".join(p for p in [addr.get("city"), addr.get("state"), addr.get("pincode")] if p)
    return "<br/>".join(p for p in [line1, city_state] if p)


def _upi_qr_image(amount: float, order_no: str) -> Image:
    uri = f"upi://pay?pa={COMPANY['upi_id']}&pn={COMPANY['name'].replace(' ', '%20')}&am={amount:.2f}&cu=INR&tn=Invoice%20{order_no}"
    qr = qrcode.QRCode(box_size=4, border=1)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Image(buf, width=26 * mm, height=26 * mm)


def build_invoice_pdf(order_id: int) -> tuple[io.BytesIO, str]:
    sb = _sb()
    order_res = (
        sb.schema("sales").from_("orders")
        .select("id, order_no, created_at, approved_at, client_id, billing_address_id, "
                "shipping_address_id, discount_amount, status")
        .eq("id", order_id).limit(1).execute()
    )
    if not order_res.data:
        raise ValueError("Order not found")
    order = order_res.data[0]
    if order["status"] != "invoiced":
        raise ValueError("Order must be approved/invoiced before an invoice can be generated")

    client = (
        sb.schema("sales").from_("clients")
        .select("id, business_name, gstin, fssai_no, primary_contact_name, primary_contact_phone")
        .eq("id", order["client_id"]).limit(1).execute().data[0]
    )

    addr_ids = [a for a in [order.get("billing_address_id"), order.get("shipping_address_id")] if a]
    addrs = {}
    if addr_ids:
        for a in sb.schema("sales").from_("addresses").select("*").in_("id", addr_ids).execute().data:
            addrs[a["id"]] = a
    billing_addr = addrs.get(order.get("billing_address_id"))
    shipping_addr = addrs.get(order.get("shipping_address_id")) or billing_addr

    lines = (
        sb.schema("sales").from_("order_lines")
        .select("quantity, unit_price, line_discount_amount, line_total, "
                 "skus(sku_code, hsn_code, gst_rate, flavours(name), pack_formats(name))")
        .eq("order_id", order_id).eq("status", "active").execute().data
    )

    is_interstate = bool(shipping_addr and (shipping_addr.get("state") or "").strip().lower()
                          != COMPANY["state"].lower())

    line_rows = []
    tax_buckets = {}  # gst_rate -> taxable amount
    total_qty = 0
    subtotal = 0.0
    for i, l in enumerate(lines, start=1):
        sku = l.get("skus") or {}
        flavour_name = (sku.get("flavours") or {}).get("name", "—")
        format_name = (sku.get("pack_formats") or {}).get("name", "")
        qty = float(l["quantity"])
        rate = float(l["unit_price"])
        gross = qty * rate
        disc_amt = float(l.get("line_discount_amount") or 0)
        net = float(l["line_total"])
        disc_pct = (disc_amt / gross * 100) if gross else 0
        gst_rate = float(sku.get("gst_rate") or 5.0)
        tax_buckets[gst_rate] = tax_buckets.get(gst_rate, 0.0) + net
        total_qty += qty
        subtotal += net
        line_rows.append([
            str(i), f"{flavour_name} - {format_name}", sku.get("hsn_code") or "—",
            f"{disc_pct:.0f}" if disc_pct else "", f"{qty:g}", f"{rate:,.2f}", f"{net:,.2f}",
        ])

    tax_rows = []
    total_tax = 0.0
    for rate, taxable in sorted(tax_buckets.items()):
        if is_interstate:
            amt = round(taxable * rate / 100, 2)
            total_tax += amt
            tax_rows.append((f"IGST {rate:g}% - Sale", amt))
        else:
            half = round(taxable * (rate / 2) / 100, 2)
            total_tax += half * 2
            tax_rows.append((f"CGST {rate / 2:g}% - Sale", half))
            tax_rows.append((f"SGST {rate / 2:g}% - Sale", half))

    raw_total = subtotal + total_tax
    grand_total = round(raw_total)
    rounded_off = grand_total - raw_total

    as_of = order.get("approved_at") or order.get("created_at")
    ledger = _client_ledger(sb, order["client_id"], as_of)

    # ── Build the PDF ────────────────────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=10 * mm, bottomMargin=10 * mm,
                             leftMargin=10 * mm, rightMargin=10 * mm)
    styles = {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=13, alignment=TA_CENTER),
        "company": ParagraphStyle("company", fontName="Helvetica-Bold", fontSize=12),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=10),
        "smallB": ParagraphStyle("smallB", fontName="Helvetica-Bold", fontSize=8.5, leading=11),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.5, leading=11),
        "cellB": ParagraphStyle("cellB", fontName="Helvetica-Bold", fontSize=8.5, leading=11),
    }

    story = [Paragraph("Tax Invoice", styles["title"]), Spacer(1, 4)]

    # Company header
    story.append(Table([[Paragraph(
        f"<b>{COMPANY['name']}</b><br/>{COMPANY['address']}, Mob : {COMPANY['mobile']}, "
        f"FSSAI No:{COMPANY['fssai']}, MSME (MICRO) :{COMPANY['msme'].split(' ')[0]}"
        f"<br/>GSTIN : {COMPANY['gstin']}",
        styles["small"])]], colWidths=[190 * mm],
        style=TableStyle([("BOX", (0, 0), (-1, -1), 0.75, colors.black), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 8)])))

    # Consignee / Buyer / Invoice meta
    consignee = Paragraph(
        f"<b>Consignee (Shipped To)</b><br/><b>{client['business_name']}</b><br/>"
        f"{_addr_block(shipping_addr)}<br/>"
        f"State : {(shipping_addr or {}).get('state', '')}   "
        f"State Code : {(shipping_addr or {}).get('state_code', '')}<br/>"
        f"GSTIN No : {(shipping_addr or {}).get('gstin') or client.get('gstin') or '—'}<br/>"
        f"Fssai No : {client.get('fssai_no') or '—'}", styles["small"])
    buyer = Paragraph(
        f"<b>Buyer (Billed To)</b><br/><b>{client['business_name']}</b><br/>"
        f"{_addr_block(billing_addr)}<br/>"
        f"State : {(billing_addr or {}).get('state', '')}   "
        f"State Code : {(billing_addr or {}).get('state_code', '')}<br/>"
        f"GSTIN No : {(billing_addr or {}).get('gstin') or client.get('gstin') or '—'}<br/>"
        f"Fssai No : {client.get('fssai_no') or '—'}", styles["small"])
    meta = Paragraph(
        f"Invoice No<br/><b>{order['order_no']}</b><br/>Dated<br/>"
        f"<b>{datetime.fromisoformat(order['created_at']).strftime('%d-%b-%y')}</b><br/>"
        f"Godown<br/><b>{COMPANY['godown']}</b><br/>Destination<br/>"
        f"<b>{(shipping_addr or {}).get('city', '') or '—'}</b>", styles["small"])
    story.append(Table([[consignee, buyer, meta]], colWidths=[76 * mm, 76 * mm, 38 * mm],
                        style=TableStyle([("BOX", (0, 0), (-1, -1), 0.75, colors.black),
                                           ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
                                           ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                           ("TOPPADDING", (0, 0), (-1, -1), 5),
                                           ("LEFTPADDING", (0, 0), (-1, -1), 6)])))

    # Line items
    item_header = [Paragraph(h, styles["smallB"]) for h in
                    ["SI.No", "Description", "HSN/SAC", "Disc %", "Qty", "Rate", "Amount"]]
    item_data = [item_header] + [[Paragraph(c, styles["cell"]) if i == 1 else
                                   Paragraph(c, ParagraphStyle("r", fontName="Helvetica", fontSize=8.5, alignment=TA_RIGHT))
                                   for i, c in enumerate(row)] for row in line_rows]
    for label, amt in tax_rows:
        item_data.append(["", "", "", "", "", label, f"{amt:,.2f}"])
    if abs(rounded_off) > 0.001:
        item_data.append(["", "", "", "", "", "Rounded Off", f"{rounded_off:,.2f}"])
    item_data.append([Paragraph("<b>Total</b>", styles["cellB"]), "", "", "", f"{total_qty:g}", "",
                       Paragraph(f"<b>{grand_total:,.2f}</b>", styles["cellB"])])
    items_tbl = Table(item_data, colWidths=[12 * mm, 70 * mm, 22 * mm, 16 * mm, 16 * mm, 22 * mm, 32 * mm],
                       repeatRows=1)
    items_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
        ("INNERGRID", (0, 0), (-1, 0), 0.5, colors.grey),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.black),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(items_tbl)

    story.append(Table([[Paragraph(f"Amount Chargable (in words)<br/><b>{amount_in_words(grand_total)}</b>",
                                    styles["small"])]], colWidths=[190 * mm],
                        style=TableStyle([("BOX", (0, 0), (-1, -1), 0.75, colors.black),
                                           ("TOPPADDING", (0, 0), (-1, -1), 5),
                                           ("LEFTPADDING", (0, 0), (-1, -1), 6)])))

    qr_img = _upi_qr_image(grand_total, order["order_no"])
    last_pay_line = (
        f"Last Payment Date : <b>{datetime.fromisoformat(ledger['last_payment_date']).strftime('%d-%b-%y')}</b><br/>"
        f"Last Payment Amount : <b>{ledger['last_payment_amount']:,.2f} Cr</b><br/>"
        if ledger["last_payment_date"] else "Last Payment Date : —<br/>"
    )
    balance_word = "Dr" if ledger["balance"] >= 0 else "Cr"
    footer = Table([[
        Paragraph(f"MSME : <b>{COMPANY['msme']}</b><br/><br/><b>Bank Details</b><br/>"
                  f"Bank Name : {COMPANY['bank_name']} AC : {COMPANY['bank_account_no']}<br/>"
                  f"IFSC Code : {COMPANY['ifsc']}<br/>Branch : {COMPANY['branch']}<br/>"
                  f"UPI Id : {COMPANY['upi_id']}", styles["small"]),
        Paragraph("<b>SCAN &amp; PAY</b>", styles["smallB"]),
        Paragraph(f"{last_pay_line}Current Balance : <b>{abs(ledger['balance']):,.2f} {balance_word}</b><br/>"
                  f"Total Payable : <b>{grand_total:,.2f} Dr</b>", styles["small"]),
    ]], colWidths=[80 * mm, 30 * mm, 80 * mm],
        style=TableStyle([("BOX", (0, 0), (-1, -1), 0.75, colors.black),
                           ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.grey),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, -1), "CENTER"),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
    story.append(footer)
    # QR image placed via a nested table cell isn't easy to inline above, so draw it directly after.
    story.append(Spacer(1, -22 * mm))
    story.append(Table([[Spacer(1, 1), qr_img, Spacer(1, 1)]], colWidths=[80 * mm, 30 * mm, 80 * mm],
                        style=TableStyle([("ALIGN", (1, 0), (1, 0), "CENTER")])))

    story.append(Spacer(1, 10))
    story.append(Paragraph(f"For {COMPANY['name']}<br/><br/><br/>Authorised Signature",
                            ParagraphStyle("sig", fontName="Helvetica", fontSize=9, alignment=TA_RIGHT)))
    story.append(Paragraph("This is Computer Generated Invoice",
                            ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=7.5,
                                           alignment=TA_CENTER, textColor=colors.grey)))

    doc.build(story)
    buf.seek(0)
    safe_client = "".join(c if c.isalnum() else "_" for c in client["business_name"])[:30]
    filename = f"{order['order_no'].replace('/', '')}_{safe_client}.pdf"
    return buf, filename
