import os
from datetime import date, datetime, timedelta, timezone
from sku_data import MOCK_PRICES, ACTIVE_SKUS

SUPABASE_URL = os.environ.get("SUPABASE_URL")
DEFAULT_PASSWORD = "test@123"  # new staff accounts must change this on first login

_PAGE_SIZE = 1000  # PostgREST's default max rows per request — must page past it explicitly.


def _fetch_all_pages(build_query) -> list:
    """build_query(start, end) must return a fresh, unexecuted query with .range(start, end)
    applied — PostgREST silently caps unbounded selects at _PAGE_SIZE rows, so anything that
    can plausibly exceed that (orders, order_lines) has to be paged through explicitly."""
    rows = []
    start = 0
    while True:
        batch = build_query(start, start + _PAGE_SIZE - 1).execute().data
        rows.extend(batch)
        if len(batch) < _PAGE_SIZE:
            break
        start += _PAGE_SIZE
    return rows

REGION_HEAD_ROLES = {
    "mumbai_head": "Mumbai",
    "pune_head": "Pune",
    "bangalore_head": "Bangalore",
    "hyderabad_head": "Hyderabad",
    "delhi_head": "Delhi",
    "roi_head": "Rest of India",
}
ROLE_LABELS = {
    "admin": "Admin",
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
# Strictly the named city itself - Thane/Navi Mumbai/Vasai-Virar are NOT part of
# "Mumbai" here even though they're in the metro area; they fall through to ROI.
_CITY_TO_REGION_ROLE = {
    "Mumbai": "mumbai_head",
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


# Order number city code — reuses the same city scoping as regional-head
# visibility, so an order's code matches whichever region head sees it.
_REGION_ROLE_TO_ORDER_CODE = {
    "mumbai_head": "MU", "pune_head": "PU", "bangalore_head": "BA",
    "hyderabad_head": "HY", "delhi_head": "DL", "roi_head": "ROI",
}


def _order_city_code(place: str) -> str:
    return _REGION_ROLE_TO_ORDER_CODE[_region_role_for_city(place)]


def _financial_year(d: date) -> str:
    """Indian FY runs April-March, e.g. May 2026 and Jan 2027 are both FY 26-27."""
    start_year = d.year if d.month >= 4 else d.year - 1
    return f"{str(start_year)[-2:]}-{str(start_year + 1)[-2:]}"

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
        .select("id, full_name, role, email, is_active, must_change_password")
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
    # "city" is entered at locality precision (e.g. "Bandra West") — the whole
    # book of business is Mumbai, so `city` itself is now a fixed "Mumbai" and
    # the actual submitted value is preserved in `locality`.
    locality = (data.get("city") or "").strip()
    state = (data.get("state") or "").strip()
    pincode = (data.get("pincode") or "").strip()

    if not line1:
        raise ValueError("Address line is required")
    if not locality:
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
        "city": "Mumbai",
        "locality": locality,
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
    for k in ("locality", "city"):
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


def _next_order_no(sb, city_code: str) -> str:
    """{CITY}{MM}/{FY}/{SEQ:04d}, e.g. MU05/26-27/1843 — sequence is scoped
    per city per financial year (Indian FY, April-March), so it resets when
    a new FY starts and each city counts independently."""
    today = date.today()
    fy = _financial_year(today)
    mm = f"{today.month:02d}"
    # City code is fixed length but LIKE needs to skip over the 2-digit month
    # regardless of code length ("MU__/26-27/%" or "ROI__/26-27/%").
    pattern = f"{city_code}__/{fy}/%"
    result = (
        sb.schema("sales").from_("orders").select("order_no")
        .like("order_no", pattern).execute()
    )
    max_seq = 0
    for row in result.data:
        try:
            max_seq = max(max_seq, int(row["order_no"].rsplit("/", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"{city_code}{mm}/{fy}/{max_seq + 1:04d}"


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

    city_code = "ROI"
    if shipping_address_id:
        addr = sb.schema("sales").from_("addresses").select("city,locality").eq("id", shipping_address_id).limit(1).execute()
        if addr.data:
            place = addr.data[0].get("locality") or addr.data[0].get("city")
            if place:
                city_code = _order_city_code(place)
    order_no = _next_order_no(sb, city_code)
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

    def build_query(start, end):
        q = (
            sb.schema("sales").from_("orders")
            .select("id, order_no, status, total_amount, created_at, client_id, salesperson_id, shipping_address_id")
            .order("created_at", desc=True)
        )
        if role != "admin" and role not in REGION_HEAD_ROLES:
            q = q.eq("created_by_user_id", user_id)
        return q.range(start, end)

    orders = _fetch_all_pages(build_query)
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
        sb.schema("sales").from_("addresses").select("id,city,locality,state").in_("id", addr_ids).execute().data
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
        place = addr.get("locality") or addr.get("city") or "—"
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


_TERMINAL_ORDER_STATUSES = {"invoiced", "rejected", "cancelled", "delivered"}
_COMPLETABLE_BLOCKED_STATUSES = {"delivered", "rejected", "cancelled"}


def get_order_lines(order_id: int, user_id: int, role: str) -> list:
    sb = _sb()
    order = (
        sb.schema("sales").from_("orders")
        .select("id, created_by_user_id, salesperson_id, shipping_address_id")
        .eq("id", order_id).limit(1).execute()
    )
    if not order.data:
        raise ValueError("Order not found")
    o = order.data[0]
    if role in REGION_HEAD_ROLES:
        addr = (
            sb.schema("sales").from_("addresses").select("city,locality")
            .eq("id", o["shipping_address_id"]).limit(1).execute()
            if o.get("shipping_address_id") else None
        )
        place = (addr.data[0].get("locality") or addr.data[0].get("city")) if addr and addr.data else None
        if _region_role_for_city(place) != role:
            raise ValueError("Not authorized to view this order")
    elif role != "admin":
        if o.get("created_by_user_id") != user_id and o.get("salesperson_id") != user_id:
            raise ValueError("Not authorized to view this order")

    lines = (
        sb.schema("sales").from_("order_lines")
        .select("id, quantity, unit_price, line_total, status, "
                "skus(sku_code, flavours(name), pack_formats(name))")
        .eq("order_id", order_id).execute().data
    )
    out = []
    for l in lines:
        sku = l.get("skus") or {}
        out.append({
            "flavour_name": (sku.get("flavours") or {}).get("name", "—"),
            "pack_format_name": (sku.get("pack_formats") or {}).get("name", "—"),
            "sku_code": sku.get("sku_code", "—"),
            "quantity": float(l["quantity"]),
            "unit_price": float(l["unit_price"]),
            "line_total": float(l["line_total"]),
            "status": l["status"],
        })
    return out


def mark_order_completed(order_id: int, user_id: int, role: str) -> dict:
    sb = _sb()
    order = (
        sb.schema("sales").from_("orders")
        .select("status, created_by_user_id, salesperson_id")
        .eq("id", order_id).limit(1).execute()
    )
    if not order.data:
        raise ValueError("Order not found")
    o = order.data[0]
    if role not in REGION_HEAD_ROLES and role != "admin":
        if o.get("created_by_user_id") != user_id and o.get("salesperson_id") != user_id:
            raise ValueError("Not authorized to update this order")
    # Completion (delivery) is independent of invoicing — an order can be invoiced
    # before or after the goods actually go out, so "invoiced" alone shouldn't
    # block marking it completed. Only these are truly final.
    if o["status"] in _COMPLETABLE_BLOCKED_STATUSES:
        raise ValueError(f"Order is already {o['status']}")
    res = sb.schema("sales").from_("orders").update({"status": "delivered"}).eq("id", order_id).execute()
    return res.data[0]


def flavour_sales_summary(user_id: int, role: str) -> dict:
    """Line-item sales data for the Insights view / flavour & SKU reports.

    Returns pre-tax product revenue (order_lines.line_total has no GST in it —
    tax is only ever applied at the order level, in orders.total_amount), plus
    a count/value of orders that have no recorded line items at all (common in
    the historical bulk-imported data) so callers can flag that gap instead of
    silently under-reporting against the order-level totals shown elsewhere.
    """
    sb = _sb()

    def build_orders_query(start, end):
        q = (
            sb.schema("sales").from_("orders")
            .select("id, created_at, total_amount, shipping_address_id, created_by_user_id, salesperson_id")
        )
        if role != "admin" and role not in REGION_HEAD_ROLES:
            q = q.eq("created_by_user_id", user_id)
        return q.range(start, end)

    orders = _fetch_all_pages(build_orders_query)
    if not orders:
        return {"lines": [], "orders_without_lines": 0, "value_without_lines": 0.0}

    addr_ids = list({o["shipping_address_id"] for o in orders if o.get("shipping_address_id")})
    addrs = {a["id"]: a for a in (
        sb.schema("sales").from_("addresses").select("id,city,locality").in_("id", addr_ids).execute().data
        if addr_ids else [])}

    def _addr_place(o):
        addr = addrs.get(o.get("shipping_address_id")) or {}
        return addr.get("locality") or addr.get("city")

    if role in REGION_HEAD_ROLES:
        orders = [o for o in orders if _region_role_for_city(_addr_place(o)) == role]

    orders_by_id = {o["id"]: o for o in orders}
    order_ids = list(orders_by_id.keys())

    lines = []
    CHUNK = 200
    for i in range(0, len(order_ids), CHUNK):
        chunk_ids = order_ids[i:i + CHUNK]

        def build_lines_query(start, end, chunk_ids=chunk_ids):
            return (
                sb.schema("sales").from_("order_lines")
                .select("order_id, quantity, line_total, skus(sku_code, flavours(name))")
                .eq("status", "active").in_("order_id", chunk_ids).range(start, end)
            )

        lines.extend(_fetch_all_pages(build_lines_query))

    out = []
    ids_with_lines = set()
    for l in lines:
        o = orders_by_id.get(l["order_id"])
        if not o:
            continue
        ids_with_lines.add(l["order_id"])
        place = _addr_place(o)
        sku = l.get("skus") or {}
        out.append({
            "flavour_name": (sku.get("flavours") or {}).get("name", "—"),
            "sku_code": sku.get("sku_code", "—"),
            "city": city_for_place(place) if place else "—",
            "created_at": o["created_at"],
            "quantity": float(l["quantity"]),
            "revenue": float(l["line_total"]),
        })

    missing = [o for o in orders if o["id"] not in ids_with_lines]
    return {
        "lines": out,
        "orders_without_lines": len(missing),
        "value_without_lines": sum(o.get("total_amount", 0) or 0 for o in missing),
    }


def approve_order(order_id: int, approved_by: int) -> dict:
    sb = _sb()
    order = sb.schema("sales").from_("orders").select("status").eq("id", order_id).limit(1).execute()
    if not order.data:
        raise ValueError("Order not found")
    if order.data[0]["status"] in _TERMINAL_ORDER_STATUSES:
        raise ValueError(f"Order is already {order.data[0]['status']}")
    row = {
        "status": "invoiced", "approved_by": approved_by,
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    res = sb.schema("sales").from_("orders").update(row).eq("id", order_id).execute()
    return res.data[0]


def reject_order(order_id: int, rejected_by: int) -> dict:
    sb = _sb()
    order = sb.schema("sales").from_("orders").select("status").eq("id", order_id).limit(1).execute()
    if not order.data:
        raise ValueError("Order not found")
    if order.data[0]["status"] in _TERMINAL_ORDER_STATUSES:
        raise ValueError(f"Order is already {order.data[0]['status']}")
    res = sb.schema("sales").from_("orders").update({"status": "rejected"}).eq("id", order_id).execute()
    return res.data[0]


def list_clients() -> list:
    sb = _sb()
    clients = (
        sb.schema("sales").from_("clients")
        .select("id, business_name, client_type, primary_contact_name, primary_contact_phone, "
                "gstin, fssai_no, addresses(id, address_type, line1, line2, city, locality, state, pincode, gstin, is_default)")
        .eq("status", "active").order("business_name").execute().data
    )
    for c in clients:
        addrs = c.get("addresses") or []
        default_addr = next((a for a in addrs if a.get("is_default")), addrs[0] if addrs else None)
        place = (default_addr or {}).get("locality") or (default_addr or {}).get("city")
        c["place"] = place or "—"
        c["city"] = city_for_place(place) if place else "Unassigned"
    return clients


def update_client(client_id: int, data: dict) -> dict:
    sb = _sb()
    updates = {}
    if "gstin" in data:
        updates["gstin"] = (data.get("gstin") or "").strip() or None
    if "fssai_no" in data:
        updates["fssai_no"] = (data.get("fssai_no") or "").strip() or None
    if not updates:
        raise ValueError("Nothing to update")
    res = sb.schema("sales").from_("clients").update(updates).eq("id", client_id).execute()
    if not res.data:
        raise ValueError("Client not found")
    return res.data[0]


def update_address(address_id: int, data: dict) -> dict:
    sb = _sb()
    updates = {}
    for key in ("line1", "line2", "state", "pincode", "gstin", "address_type"):
        if key in data:
            updates[key] = (data.get(key) or "").strip() or None
    # "city" here means locality precision (e.g. "Bandra West") — the real
    # `city` column stays a fixed "Mumbai", so route edits to `locality` instead.
    if "city" in data:
        updates["locality"] = (data.get("city") or "").strip() or None
    if updates.get("state"):
        updates["state_code"] = _state_code_for(updates["state"])
    if "is_default" in data:
        updates["is_default"] = bool(data["is_default"])
    if not updates:
        raise ValueError("Nothing to update")
    res = sb.schema("sales").from_("addresses").update(updates).eq("id", address_id).execute()
    if not res.data:
        raise ValueError("Address not found")
    return res.data[0]


VALID_STAFF_ROLES = {"salesperson", "admin", *REGION_HEAD_ROLES}
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
        "region": region, "must_change_password": True,
    }
    res = sb.schema("sales").from_("users").insert(row).execute()
    staff = res.data[0]

    try:
        sb.auth.admin.create_user({
            "email": email, "password": DEFAULT_PASSWORD, "email_confirm": True,
            "user_metadata": {"full_name": full_name},
        })
    except Exception as e:
        staff["auth_error"] = str(e)
    return staff


def set_user_password(auth_user_id: str, new_password: str) -> None:
    sb = _sb()
    sb.auth.admin.update_user_by_id(auth_user_id, {"password": new_password})


def mark_password_changed(staff_id: int) -> None:
    sb = _sb()
    sb.schema("sales").from_("users").update({"must_change_password": False}).eq("id", staff_id).execute()


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


# ── Admin: SKU stock (sourced from the production schema, no inventory
#    tracking lives in sales) ────────────────────────────────────────────────

def list_sku_stock() -> list:
    sb = _sb()
    fg_rows = (
        sb.schema("production").from_("v_fg_stock")
        .select("product_name, unit, qty_on_hand, status")
        .execute().data
    )
    # No FK between schemas — production.v_fg_stock only has free-text
    # product_name/unit, so match against sales SKUs by (flavour, format) name.
    stock_by_key = {(r["product_name"].strip().lower(), r["unit"].strip().lower()): r for r in fg_rows}
    out = []
    for s in ACTIVE_SKUS:
        key = (s["flavour_name"].strip().lower(), s["pack_format_name"].strip().lower())
        fg = stock_by_key.get(key)
        out.append({
            "sku_code": s["sku_code"], "flavour_name": s["flavour_name"],
            "pack_format_name": s["pack_format_name"],
            "qty_on_hand": float(fg["qty_on_hand"]) if fg else None,
            "stock_status": fg["status"] if fg else "not_tracked",
        })
    out.sort(key=lambda r: (r["flavour_name"], r["pack_format_name"]))
    return out


# ── Admin: flavour + SKU pricing management ─────────────────────────────────

_SKU_CODE_FORMAT_TAGS = {1: "4L", 2: "12SQ", 3: "Samp", 4: "Extra", 5: "B2BAD", 6: "500ML"}


def list_pack_formats() -> list:
    sb = _sb()
    return (
        sb.schema("sales").from_("pack_formats").select("id,name")
        .eq("status", "active").order("id").execute().data
    )


def _current_prices_by_sku() -> dict:
    """One batched query for every SKU's currently-effective price, instead of
    a separate get_sku_price() network round-trip per SKU (was the cause of a
    ~60s load for the Flavours admin tab with 80+ SKUs — classic N+1)."""
    sb = _sb()
    today = date.today().isoformat()
    rows = (
        sb.schema("sales").from_("sku_prices").select("sku_id,price,effective_from")
        .lte("effective_from", today)
        .or_(f"effective_to.is.null,effective_to.gte.{today}")
        .order("effective_from", desc=True)
        .execute().data
    )
    out = {}
    for r in rows:
        out.setdefault(r["sku_id"], float(r["price"]))  # first (most recent) wins
    return out


def list_flavours_admin() -> list:
    sb = _sb()
    flavours = sb.schema("sales").from_("flavours").select("id,name,status").order("name").execute().data
    skus = (
        sb.schema("sales").from_("skus")
        .select("id,sku_code,flavour_id,pack_format_id,status,hsn_code,gst_rate,pack_formats(name)")
        .execute().data
    )
    prices = _current_prices_by_sku()
    by_flavour = {}
    for s in skus:
        by_flavour.setdefault(s["flavour_id"], []).append({
            "id": s["id"], "sku_code": s["sku_code"],
            "pack_format_id": s["pack_format_id"],
            "pack_format_name": s["pack_formats"]["name"] if s.get("pack_formats") else "",
            "status": s["status"],
            "price": prices.get(s["id"], MOCK_PRICES.get(s["pack_format_id"], 0.0)),
            "hsn_code": s.get("hsn_code") or "",
            "gst_rate": float(s["gst_rate"]) if s.get("gst_rate") is not None else 5.0,
        })
    return [{
        "id": f["id"], "name": f["name"], "status": f["status"],
        "skus": by_flavour.get(f["id"], []),
    } for f in flavours]


def create_flavour(name: str, pack_format_ids: list, created_by: int) -> dict:
    sb = _sb()
    name = (name or "").strip()
    if not name:
        raise ValueError("Flavour name is required")
    if not pack_format_ids:
        raise ValueError("Select at least one pack format")

    existing = sb.schema("sales").from_("flavours").select("id").ilike("name", name).execute()
    if existing.data:
        raise ValueError(f"A flavour already exists with this name: {name}")

    fres = sb.schema("sales").from_("flavours").insert({"name": name}).execute()
    flavour_id = fres.data[0]["id"]

    sku_rows = [_new_sku_row(flavour_id, name, pfid) for pfid in pack_format_ids]
    sb.schema("sales").from_("skus").insert(sku_rows).execute()

    return {"id": flavour_id, "name": name}


_DEFAULT_HSN_CODE = "21050000"  # Ice cream and other edible ice


def _new_sku_row(flavour_id: int, flavour_name: str, pack_format_id: int) -> dict:
    prefix = "".join(ch for ch in flavour_name.upper() if ch.isalpha())[:3] or "SKU"
    tag = _SKU_CODE_FORMAT_TAGS.get(pack_format_id, str(pack_format_id))
    return {
        "flavour_id": flavour_id, "pack_format_id": pack_format_id,
        "sku_code": f"{prefix}-{tag}-{flavour_id}", "hsn_code": _DEFAULT_HSN_CODE,
    }


def update_flavour(flavour_id: int, data: dict) -> dict:
    sb = _sb()
    updates = {}
    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            raise ValueError("Flavour name is required")
        updates["name"] = name
    if "status" in data:
        if data["status"] not in ("active", "inactive", "discontinued"):
            raise ValueError("Invalid status")
        updates["status"] = data["status"]
    if not updates:
        raise ValueError("Nothing to update")

    res = sb.schema("sales").from_("flavours").update(updates).eq("id", flavour_id).execute()
    if not res.data:
        raise ValueError("Flavour not found")
    return res.data[0]


def set_sku_price(sku_id: int, price: float, set_by: int) -> dict:
    if price < 0:
        raise ValueError("Price must be non-negative")
    sb = _sb()
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    # Close out whatever price row is currently open for this SKU, then open
    # a new one from today — so it takes effect immediately for new orders,
    # without erasing price history.
    sb.schema("sales").from_("sku_prices").update({"effective_to": yesterday}) \
        .eq("sku_id", sku_id).is_("effective_to", "null").execute()
    row = {
        "sku_id": sku_id, "price": price, "currency": "INR",
        "effective_from": today, "created_by": set_by,
    }
    res = sb.schema("sales").from_("sku_prices").insert(row).execute()
    return res.data[0]


def add_sku_to_flavour(flavour_id: int, pack_format_id: int) -> dict:
    sb = _sb()
    flavour = sb.schema("sales").from_("flavours").select("id,name").eq("id", flavour_id).limit(1).execute()
    if not flavour.data:
        raise ValueError("Flavour not found")

    existing = (
        sb.schema("sales").from_("skus").select("id,status")
        .eq("flavour_id", flavour_id).eq("pack_format_id", pack_format_id).execute()
    )
    if existing.data:
        raise ValueError("This flavour already has a SKU for that pack format — reactivate it instead of adding a new one")

    row = _new_sku_row(flavour_id, flavour.data[0]["name"], pack_format_id)
    res = sb.schema("sales").from_("skus").insert(row).execute()
    return res.data[0]


def set_sku_status(sku_id: int, status: str) -> dict:
    if status not in ("active", "inactive", "discontinued"):
        raise ValueError("Invalid status")
    sb = _sb()
    res = sb.schema("sales").from_("skus").update({"status": status}).eq("id", sku_id).execute()
    if not res.data:
        raise ValueError("SKU not found")
    return res.data[0]


