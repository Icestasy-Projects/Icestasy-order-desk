import os
from datetime import date
from sku_data import MOCK_PRICES

SUPABASE_URL = os.environ.get("SUPABASE_URL")


def _sb():
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not SUPABASE_URL or not key:
        raise RuntimeError("Supabase not configured — set SUPABASE_URL and SUPABASE_SERVICE_KEY")
    from supabase import create_client
    return create_client(SUPABASE_URL, key)


def search_clients(query: str) -> list:
    q = query.strip()
    if not q:
        return []
    sb = _sb()
    result = (
        sb.schema("sales").from_("clients")
        .select("id, business_name, client_type, default_payment_mode, primary_contact_name, primary_contact_phone, gstin")
        .or_(f"business_name.ilike.%{q}%,primary_contact_name.ilike.%{q}%,primary_contact_phone.ilike.%{q}%,gstin.ilike.%{q}%")
        .eq("status", "active").limit(8).execute()
    )
    return result.data


def get_client_addresses(client_id: int) -> list:
    sb = _sb()
    return sb.schema("sales").from_("addresses").select("*").eq("client_id", client_id).execute().data


def addr_label(addr: dict) -> str:
    parts = []
    for k in ("label", "nickname", "address_type", "type"):
        if addr.get(k):
            parts.append(str(addr[k])); break
    for k in ("address_line1", "line1", "street", "line_1"):
        if addr.get(k):
            parts.append(str(addr[k])); break
    for k in ("city",):
        if addr.get(k):
            parts.append(str(addr[k])); break
    return ", ".join(parts) if parts else f"Address #{addr.get('id','?')}"


def get_sku_price(sku_id: int, pack_format_id: int) -> float:
    try:
        sb = _sb()
        today = date.today().isoformat()
        result = (
            sb.schema("sales").from_("sku_prices").select("price")
            .eq("sku_id", sku_id).lte("effective_from", today)
            .or_(f"effective_to.is.null,effective_to.gte.{today}")
            .order("effective_from", desc=True).limit(1).execute()
        )
        if result.data:
            return float(result.data[0]["price"])
    except Exception:
        pass
    return MOCK_PRICES.get(pack_format_id, 0.0)


def _next_order_no(sb) -> str:
    year = date.today().year
    result = sb.schema("sales").from_("orders").select("order_no").order("id", desc=True).limit(1).execute()
    if result.data:
        last = result.data[0]["order_no"]
        try:
            num = int(last.split("-")[2]) + 1
        except (IndexError, ValueError):
            num = 1
        return f"ORD-{year}-{num:06d}"
    return f"ORD-{year}-000001"


def create_order(client_id, payment_mode, lines, billing_address_id=None, shipping_address_id=None, notes=None):
    sb = _sb()
    subtotal = sum(l["quantity"] * l["unit_price"] for l in lines)
    discount = sum(l.get("line_discount", 0.0) * l["quantity"] for l in lines)
    total = subtotal - discount
    order_no = _next_order_no(sb)
    order_row = {
        "order_no": order_no, "client_id": client_id,
        "channel": "whatsapp", "order_type": "commercial",
        "payment_mode": payment_mode,
        "billing_address_id": billing_address_id,
        "shipping_address_id": shipping_address_id,
        "status": "draft", "salesperson_id": 1,
        "placed_by_client": False, "source": "whatsapp_ai",
        "is_urgent": False,
        "subtotal_amount": str(subtotal), "discount_amount": str(discount),
        "tax_amount": "0.00", "total_amount": str(total), "notes": notes,
    }
    order_res = sb.schema("sales").from_("orders").insert(order_row).execute()
    order_id = order_res.data[0]["id"]
    line_rows = []
    for l in lines:
        qty = l["quantity"]; price = l["unit_price"]
        disc = l.get("line_discount", 0.0)
        line_rows.append({
            "order_id": order_id, "sku_id": l["sku_id"],
            "quantity": str(qty), "unit_price": str(price),
            "line_discount_amount": str(disc * qty),
            "line_total": str(qty * price - disc * qty), "status": "active",
        })
    sb.schema("sales").from_("order_lines").insert(line_rows).execute()
    return {**order_res.data[0], "subtotal": subtotal, "discount": discount, "total": total,
            "lines": [{"sku_code": l["sku_code"], "flavour_name": l["flavour_name"],
                       "format_name": l["format_name"], "quantity": l["quantity"],
                       "unit_price": l["unit_price"],
                       "line_total": l["quantity"] * l["unit_price"] - l.get("line_discount", 0.0) * l["quantity"]}
                      for l in lines]}