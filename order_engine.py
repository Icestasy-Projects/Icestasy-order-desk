import os
from datetime import date, datetime, timezone
from sku_data import MOCK_PRICES

SUPABASE_URL = os.environ.get("SUPABASE_URL")

REGION_HEAD_ROLES = {
    "mumbai_head": "Mumbai",
    "pune_head": "Pune",
    "bangalore_head": "Bangalore",
    "hyderabad_head": "Hyderabad",
    "delhi_head": "Delhi",
    "roi_head": "Rest of India",
}
ROLE_LABELS = {
    "manager": "Head of Sales",
    "onboarding": "Client Onboarding",
    "salesperson": "Sales Team Member",
    **{role: f"{label} Head" for role, label in REGION_HEAD_ROLES.items()},
}
# Address "city" values are entered at locality/neighbourhood precision (e.g. "Bandra West"),
# not actual city precision — this rolls localities up to their real city for reporting.
_PLACE_TO_CITY = {
    **{p: "Mumbai" for p in [
        "mumbai", "bandra west", "bandra east", "bandra", "andheri west", "andheri east",
        "andheri", "juhu", "chembur", "malad west", "malad east", "malad", "lower parel",
        "dadar west", "dadar east", "dadar", "mulund west", "mulund east", "mulund",
        "goregaon east", "goregaon west", "goregaon east (oberoi)", "kandivali east",
        "kandivali west", "kandivali", "ghatkopar west", "ghatkopar east", "vile parle east",
        "vile parle west", "vile parle", "powai", "fort", "worli", "colaba", "parel",
        "vikhroli", "santacruz west", "santacruz east", "santacruz", "dahisar east",
        "dahisar west", "dahisar", "tardeo", "bkc", "khar", "khar west", "kurla",
        "kurla west", "churchgate", "marol", "matunga east", "matunga", "kalbadevi",
        "girgaon", "sewri", "mahim", "zaveri bazaar", "mumbai central", "saki naka",
        "sion", "charni road", "azad nagar", "marine lines", "borivali east",
        "borivali west", "borivali", "versova", "grant road", "nariman point",
        "babulnath", "prabhadevi", "mahalaxmi", "bhandup", "oshiwara", "marine drive",
        "jogeshwari west", "jogeshwari", "vidyavihar", "cuffe parade",
        "mohammad ali road", "pydhonie", "byculla",
    ]},
    **{p: "Thane" for p in [
        "thane", "thane west", "thane east", "thane west (viviana mall)",
        "thane west (hiranandani)", "dombivali east", "dombivali",
    ]},
    **{p: "Navi Mumbai" for p in [
        "navi mumbai", "vashi", "kharghar", "kopar khairane", "cbd belapur", "airoli",
        "seawoods", "ghansoli", "kamothe",
    ]},
    **{p: "Vasai-Virar" for p in [
        "vasai", "virar", "virar west", "nalasopara", "mira road", "bhayandar",
    ]},
    **{p: "Bangalore" for p in ["bangalore", "bengaluru"]},
    **{p: "Delhi" for p in ["delhi", "new delhi"]},
}

# For regional-head scoping: which region-head role owns each real city.
_CITY_TO_REGION_ROLE = {
    "Mumbai": "mumbai_head", "Thane": "mumbai_head",
    "Navi Mumbai": "mumbai_head", "Vasai-Virar": "mumbai_head",
    "Pune": "pune_head",
    "Bangalore": "bangalore_head",
    "Hyderabad": "hyderabad_head",
    "Delhi": "delhi_head",
}


def city_for_place(place: str) -> str:
    p = (place or "").strip().lower()
    return _PLACE_TO_CITY.get(p, (place or "").strip() or "—")


def _region_role_for_city(place: str) -> str:
    return _CITY_TO_REGION_ROLE.get(city_for_place(place), "roi_head")

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


def get_staff_by_email(email: str) -> dict | None:
    sb = _sb()
    result = (
        sb.schema("sales").from_("users")
        .select("id, full_name, role, email, is_active")
        .eq("email", email.strip().lower()).limit(1).execute()
    )
    return result.data[0] if result.data else None


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


def register_client(data: dict, registered_by: int) -> dict:
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
        "registered_by": registered_by,
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


def add_order_collateral(sb, order_id: int, collateral: list) -> list:
    rows = [{
        "order_id": order_id,
        "collateral_type": c["type"],
        "quantity": c["quantity"],
        "notes": (c.get("notes") or "").strip() or None,
    } for c in collateral]
    res = sb.schema("sales").from_("order_collateral").insert(rows).execute()
    return res.data


def create_order(client_id, payment_mode, lines, user_id, billing_address_id=None, shipping_address_id=None, notes=None, collateral=None):
    sb = _sb()
    payment_mode = payment_mode or "advance"  # payment_mode is NOT NULL; not asked for collateral-only orders
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
        "status": "draft", "salesperson_id": user_id, "created_by_user_id": user_id,
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
    if line_rows:
        sb.schema("sales").from_("order_lines").insert(line_rows).execute()

    collateral_out = []
    if collateral:
        saved = add_order_collateral(sb, order_id, collateral)
        collateral_out = [{"type": c["collateral_type"], "quantity": c["quantity"], "notes": c.get("notes")}
                           for c in saved]

    return {**order_res.data[0], "subtotal": subtotal, "discount": discount, "total": total,
            "lines": [{"sku_code": l["sku_code"], "flavour_name": l["flavour_name"],
                       "format_name": l["format_name"], "quantity": l["quantity"],
                       "unit_price": l["unit_price"],
                       "line_total": l["quantity"] * l["unit_price"] - l.get("line_discount", 0.0) * l["quantity"]}
                      for l in lines],
            "collateral": collateral_out}


def list_dashboard_orders(user_id: int, role: str) -> list:
    sb = _sb()
    q = (
        sb.schema("sales").from_("orders")
        .select("id, order_no, status, total_amount, created_at, client_id, salesperson_id, shipping_address_id")
        .order("created_at", desc=True)
    )
    if role != "manager" and role not in REGION_HEAD_ROLES:
        q = q.eq("created_by_user_id", user_id)
    orders = q.execute().data
    if not orders:
        return []

    client_ids = list({o["client_id"] for o in orders if o.get("client_id")})
    addr_ids = list({o["shipping_address_id"] for o in orders if o.get("shipping_address_id")})
    sp_ids = list({o["salesperson_id"] for o in orders if o.get("salesperson_id")})
    order_ids = [o["id"] for o in orders]

    clients = {c["id"]: c for c in (
        sb.schema("sales").from_("clients").select("id,business_name").in_("id", client_ids).execute().data
        if client_ids else [])}
    addrs = {a["id"]: a for a in (
        sb.schema("sales").from_("addresses").select("id,city,state").in_("id", addr_ids).execute().data
        if addr_ids else [])}
    staff = {u["id"]: u for u in (
        sb.schema("sales").from_("users").select("id,full_name").in_("id", sp_ids).execute().data
        if sp_ids else [])}
    payments = {}
    if order_ids:
        for p in (
            sb.schema("sales").from_("payments").select("order_id,status,amount,payment_type,received_at")
            .in_("order_id", order_ids).order("received_at", desc=True).execute().data
        ):
            payments.setdefault(p["order_id"], p)  # most recent per order (already sorted desc)

    out = []
    for o in orders:
        client = clients.get(o.get("client_id"), {})
        addr = addrs.get(o.get("shipping_address_id"), {})
        sp = staff.get(o.get("salesperson_id"), {})
        payment = payments.get(o["id"])
        place = addr.get("city") or "—"
        out.append({
            "id": o["id"], "order_no": o["order_no"], "status": o["status"],
            "total_amount": float(o["total_amount"]), "created_at": o["created_at"],
            "client_name": client.get("business_name", "—"),
            "place": place,
            "city": city_for_place(place) if place != "—" else "—",
            "salesperson_name": sp.get("full_name", "—"),
            "payment_status": payment["status"] if payment else "not_recorded",
        })

    if role in REGION_HEAD_ROLES:
        out = [o for o in out if _region_role_for_city(o["place"]) == role]
    return out


def mark_payment_received(order_id: int, received_by: int) -> dict:
    sb = _sb()
    order = sb.schema("sales").from_("orders").select("total_amount").eq("id", order_id).limit(1).execute()
    if not order.data:
        raise ValueError("Order not found")
    row = {
        "order_id": order_id, "payment_type": "full",
        "amount": order.data[0]["total_amount"],
        "status": "received", "received_by": received_by,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    res = sb.schema("sales").from_("payments").insert(row).execute()
    return res.data[0]


VALID_STAFF_ROLES = {"salesperson", "manager", "onboarding", *REGION_HEAD_ROLES}
VALID_REGIONS = set(REGION_HEAD_ROLES.values())


def _clean_region(value) -> str | None:
    region = (value or "").strip() or None
    if region and region not in VALID_REGIONS:
        raise ValueError(f"Invalid region: {region}")
    return region


def list_team(region: str | None = None) -> list:
    sb = _sb()
    q = (
        sb.schema("sales").from_("users")
        .select("id,full_name,role,email,is_active,created_at,region")
        .order("full_name")
    )
    if region:
        q = q.eq("region", region)
    return q.execute().data


def create_team_member(data: dict) -> dict:
    sb = _sb()
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    role = data.get("role") or "salesperson"
    region = _clean_region(data.get("region"))

    if not full_name:
        raise ValueError("Full name is required")
    if not email:
        raise ValueError("Email is required")
    if role not in VALID_STAFF_ROLES:
        raise ValueError("Invalid role")

    existing = sb.schema("sales").from_("users").select("id").eq("email", email).execute()
    if existing.data:
        raise ValueError(f"A staff member already exists with this email: {email}")

    row = {
        "full_name": full_name, "role": role, "email": email,
        "phone": (data.get("phone") or "").strip() or None,
        "region": region,
    }
    res = sb.schema("sales").from_("users").insert(row).execute()
    staff = res.data[0]

    try:
        sb.auth.admin.invite_user_by_email(email)
    except Exception as e:
        staff["invite_error"] = str(e)
    return staff


def update_team_member(staff_id: int, data: dict) -> dict:
    sb = _sb()
    updates = {}
    if "role" in data:
        role = data["role"]
        if role not in VALID_STAFF_ROLES:
            raise ValueError("Invalid role")
        updates["role"] = role
    if "region" in data:
        updates["region"] = _clean_region(data.get("region"))
    if "is_active" in data:
        updates["is_active"] = bool(data["is_active"])
    if not updates:
        raise ValueError("Nothing to update")

    res = sb.schema("sales").from_("users").update(updates).eq("id", staff_id).execute()
    if not res.data:
        raise ValueError("Staff member not found")
    return res.data[0]
