import os
from datetime import date
from sku_data import MOCK_PRICES

SUPABASE_URL = os.environ.get("SUPABASE_URL")

INDIA_STATE_CODES = {
    "jammu and kashmir": "01", "himachal pradesh": "02", "punjab": "03",
    "chandigarh": "04", "uttarakhand": "05", "haryana": "06", "delhi": "07",
    "rajasthan": "08", "uttar pradesh": "09", "bihar": "10", "sikkim": "11",
    "arunachal pradesh": "12", "nagaland": "13", "manipur": "14", "mizoram": "15",
    "tripura": "16", "meghalaya": "17", "assam": "18", "west bengal": "19",
    "jharkhand": "20", "odisha": "21", "chhattisgarh": "22", "madhya pradesh": "23",
    "gujarat": "24", "daman and diu": "25", "dadra and nagar haveli": "26",
    "maharashtra": "27", "karnataka": "29", "goa": "30", "lakshadweep": "31",
    "kerala": "32", "tamil nadu": "33", "puducherry": "34",
    "andaman and nicobar islands": "35", "telangana": "36", "andhra pradesh": "37",
    "ladakh": "38",
}


def _state_code_for(state_name: str) -> str:
    return INDIA_STATE_CODES.get(state_name.strip().lower(), "00")


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


def register_client(data: dict) -> dict:
    sb = _sb()
    business_name = (data.get("business_name") or "").strip()
    phone = (data.get("primary_contact_phone") or "").strip() or None
    gstin = (data.get("gstin") or "").strip() or None
    fssai_no = (data.get("fssai_no") or "").strip() or None

    if not business_name:
        raise ValueError("Business name is required")
    if not phone:
        raise ValueError("Phone number is required")

    or_parts = [f"primary_contact_phone.eq.{phone}"]
    if gstin:
        or_parts.append(f"gstin.eq.{gstin}")
    if fssai_no:
        or_parts.append(f"fssai_no.eq.{fssai_no}")

    existing = (
        sb.schema("sales").from_("clients")
        .select("id, business_name, gstin, fssai_no, primary_contact_phone")
        .or_(",".join(or_parts))
        .execute()
    )
    if existing.data:
        dupe = existing.data[0]
        if gstin and dupe.get("gstin") == gstin:
            reason = "GSTIN"
        elif fssai_no and dupe.get("fssai_no") == fssai_no:
            reason = "FSSAI No"
        else:
            reason = "phone number"
        raise ValueError(f"A client already exists with this {reason}: {dupe['business_name']}")

    row = {
        "business_name": business_name,
        "client_type": data.get("client_type") or "horeca",
        "is_roi_dealer": False,
        "gstin": gstin,
        "fssai_no": fssai_no,
        "primary_contact_name": (data.get("primary_contact_name") or "").strip() or None,
        "primary_contact_phone": phone,
        "email": (data.get("email") or "").strip() or None,
        "credit_terms_days": 0,
        "default_payment_mode": data.get("default_payment_mode") or "advance",
        "status": "active",
        "registered_by": 1,
    }
    res = sb.schema("sales").from_("clients").insert(row).execute()
    return res.data[0]


def get_client_addresses(client_id: int) -> list:
    sb = _sb()
    return sb.schema("sales").from_("addresses").select("*").eq("client_id", client_id).execute().data


def create_address(client_id: int, data: dict) -> dict:
    sb = _sb()
    line1 = (data.get("line1") or "").strip()
    city = (data.get("city") or "").strip()
    state = (data.get("state") or "").strip()
    pincode = (data.get("pincode") or "").strip()

    if not line1:
        raise ValueError("Address line is required")
    if not city:
        raise ValueError("City is required")
    if not state:
        raise ValueError("State is required")
    if not pincode:
        raise ValueError("Pincode is required")

    row = {
        "client_id": client_id,
        "address_type": data.get("address_type") or "shipping",
        "gstin": (data.get("gstin") or "").strip() or None,
        "line1": line1,
        "line2": (data.get("line2") or "").strip() or None,
        "city": city,
        "state": state,
        "state_code": _state_code_for(state),
        "pincode": pincode,
        "is_default": bool(data.get("is_default", False)),
    }
    res = sb.schema("sales").from_("addresses").insert(row).execute()
    return res.data[0]


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


def list_collateral() -> list:
    sb = _sb()
    return (
        sb.schema("sales").from_("order_collateral")
        .select("*").order("created_at", desc=True).execute().data
    )


def create_collateral(data: dict) -> dict:
    sb = _sb()
    title = (data.get("title") or "").strip()
    file_url = (data.get("file_url") or "").strip()
    if not title:
        raise ValueError("Title is required")
    if not file_url:
        raise ValueError("File URL is required")
    row = {
        "title": title,
        "description": (data.get("description") or "").strip() or None,
        "category": (data.get("category") or "general").strip() or "general",
        "file_url": file_url,
        "created_by": 1,
    }
    res = sb.schema("sales").from_("order_collateral").insert(row).execute()
    return res.data[0]


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
