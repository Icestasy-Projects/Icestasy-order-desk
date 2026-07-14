import json
import os
from datetime import date
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from parser import parse_order_text
from order_engine import (
    search_clients, get_client_addresses, addr_label, create_order,
    register_client, create_address, get_staff_by_email,
    list_dashboard_orders, mark_payment_received, list_team, create_team_member,
    update_team_member, REGION_HEAD_ROLES, ROLE_LABELS,
    set_user_password, mark_password_changed,
    approve_order, reject_order, list_clients,
    list_sku_stock, list_flavours_admin, create_flavour, update_flavour,
    set_sku_price, list_pack_formats, add_sku_to_flavour, set_sku_status,
    update_client, update_address, set_sku_hsn_gst,
)
from invoicing import build_invoice_pdf
from reports import build_orders_workbook

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    # A random fallback breaks sessions on serverless: each request can hit a different
    # cold-started instance with its own random key, invalidating every other instance's cookies.
    raise RuntimeError("SECRET_KEY environment variable must be set to a persistent value")

PUBLIC_ENDPOINTS = {"login", "static"}
PASSWORD_CHANGE_ENDPOINTS = {"login", "static", "change_password", "logout"}
ADMIN_ROLE = "admin"  # unified role: full access, add clients, approve/reject orders for invoicing
# Admin sees everything; regional heads see their region's orders/team, not just their own.
BROAD_VIEW_ROLES = {ADMIN_ROLE, *REGION_HEAD_ROLES}
ROLE_LABELS_JSON = json.dumps(ROLE_LABELS)


def _auth_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase auth not configured — set SUPABASE_URL and SUPABASE_ANON_KEY")
    return create_client(url, key)


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ENDPOINTS or request.path.startswith("/static/"):
        return
    if not session.get("user_id"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "unauthorized"}), 401
        return redirect(url_for("login"))
    if session.get("must_change_password") and request.endpoint not in PASSWORD_CHANGE_ENDPOINTS:
        if request.path.startswith("/api/"):
            return jsonify({"error": "password_change_required"}), 403
        return redirect(url_for("change_password"))


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != ADMIN_ROLE:
            return jsonify({"ok": False, "error": "Admin access required"}), 403
        return view(*args, **kwargs)
    return wrapped


def broad_view_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") not in BROAD_VIEW_ROLES:
            return jsonify({"error": "forbidden"}), 403
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("change_password" if session.get("must_change_password") else "index"))
        return render_template("login.html", error=request.args.get("error"))

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    try:
        sb = _auth_client()
        result = sb.auth.sign_in_with_password({"email": email, "password": password})
        staff = get_staff_by_email(result.user.email)
        if not staff or not staff["is_active"]:
            return redirect(url_for("login", error="Your account is not registered as staff. Contact your Head of Sales."))
        session["user_email"] = result.user.email
        session["user_id"] = staff["id"]
        session["role"] = staff["role"]
        session["full_name"] = staff["full_name"]
        session["auth_user_id"] = result.user.id
        session["must_change_password"] = staff["must_change_password"]
    except Exception:
        return redirect(url_for("login", error="Invalid email or password"))
    return redirect(url_for("index"))


@app.after_request
def add_no_cache_headers(response):
    # Prevent the browser's back/forward cache from showing a stale login or
    # authenticated page after a login/logout state change — always re-check
    # with the server instead of rendering a cached snapshot.
    if not request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if request.method == "GET":
        return render_template("change_password.html", error=request.args.get("error"),
                                forced=session.get("must_change_password", False))

    new_password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")
    if len(new_password) < 8:
        return redirect(url_for("change_password", error="Password must be at least 8 characters"))
    if new_password != confirm:
        return redirect(url_for("change_password", error="Passwords do not match"))

    try:
        set_user_password(session["auth_user_id"], new_password)
        mark_password_changed(session["user_id"])
        session["must_change_password"] = False
    except Exception as e:
        return redirect(url_for("change_password", error=str(e)))
    return redirect(url_for("index"))


@app.route("/")
def index():
    role = session.get("role")
    return render_template("dashboard.html", user_email=session.get("user_email"),
                            full_name=session.get("full_name"), role=role,
                            role_label=ROLE_LABELS.get(role, role),
                            is_admin=role == ADMIN_ROLE,
                            can_view_team=role in BROAD_VIEW_ROLES,
                            role_labels_json=ROLE_LABELS_JSON,
                            region_options_json=json.dumps(list(REGION_HEAD_ROLES.values())),
                            region_head_roles_json=json.dumps(REGION_HEAD_ROLES))


@app.route("/new-order")
def new_order():
    role = session.get("role")
    return render_template("index.html", user_email=session.get("user_email"),
                            full_name=session.get("full_name"), role=role,
                            is_admin=role == ADMIN_ROLE)


@app.route("/api/parse", methods=["POST"])
def api_parse():
    body = request.get_json(force=True)
    text = body.get("text", "").strip()
    if not text:
        return jsonify({"error": "empty"}), 400
    result = parse_order_text(text)
    # Serialise — remove circular refs
    for item in result["items"]:
        for c in item["candidates"]:
            c.pop("_sa_instance_state", None)
    return jsonify(result)


@app.route("/api/clients/search")
def api_clients():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"clients": []})
    try:
        clients = search_clients(q)
        return jsonify({"clients": clients})
    except RuntimeError as e:
        return jsonify({"clients": [], "error": str(e)}), 200
    except Exception as e:
        return jsonify({"clients": [], "error": str(e)}), 200


@app.route("/api/clients")
def api_clients_list():
    try:
        return jsonify({"clients": list_clients()})
    except Exception as e:
        return jsonify({"clients": [], "error": str(e)}), 200


@app.route("/api/clients", methods=["POST"])
@admin_required
def api_register_client():
    body = request.get_json(force=True)
    try:
        client = register_client(body, registered_by=session["user_id"])
        return jsonify({"ok": True, "client": client})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/clients/<int:client_id>/addresses")
def api_addresses(client_id):
    try:
        addrs = get_client_addresses(client_id)
        return jsonify({"addresses": [{"id": a["id"], "label": addr_label(a)} for a in addrs]})
    except Exception as e:
        return jsonify({"addresses": [], "error": str(e)}), 200


@app.route("/api/clients/<int:client_id>/addresses", methods=["POST"])
def api_create_address(client_id):
    body = request.get_json(force=True)
    try:
        addr = create_address(client_id, body)
        return jsonify({"ok": True, "address": {"id": addr["id"], "label": addr_label(addr)}})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/orders", methods=["POST"])
def api_orders():
    body = request.get_json(force=True)
    try:
        order = create_order(
            client_id=body["client_id"],
            payment_mode=body["payment_mode"],
            lines=body["lines"],
            user_id=session["user_id"],
            billing_address_id=body.get("billing_address_id"),
            shipping_address_id=body.get("shipping_address_id"),
            notes=body.get("notes"),
            collateral=body.get("collateral"),
        )
        return jsonify({"ok": True, "order": order})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/dashboard/orders")
def api_dashboard_orders():
    try:
        orders = list_dashboard_orders(user_id=session["user_id"], role=session["role"])
        return jsonify({"orders": orders})
    except Exception as e:
        return jsonify({"orders": [], "error": str(e)}), 200


@app.route("/api/dashboard/export")
def api_dashboard_export():
    role = session["role"]
    orders = list_dashboard_orders(user_id=session["user_id"], role=role)
    report_type = request.args.get("type", "all")
    date_from = request.args.get("from") or None
    date_to = request.args.get("to") or None
    buf = build_orders_workbook(orders, role_label=ROLE_LABELS.get(role, role),
                                 full_name=session.get("full_name") or "",
                                 report_type=report_type, date_from=date_from, date_to=date_to)
    filename = f"icestasy-orders-{report_type}-{date.today().isoformat()}.xlsx"
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                      as_attachment=True, download_name=filename)


@app.route("/api/dashboard/orders/<int:order_id>/mark-paid", methods=["POST"])
@broad_view_required
def api_mark_paid(order_id):
    try:
        payment = mark_payment_received(order_id, received_by=session["user_id"])
        return jsonify({"ok": True, "payment": payment})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/dashboard/orders/<int:order_id>/approve", methods=["POST"])
@admin_required
def api_approve_order(order_id):
    try:
        order = approve_order(order_id, approved_by=session["user_id"])
        return jsonify({"ok": True, "order": order})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/dashboard/orders/<int:order_id>/reject", methods=["POST"])
@admin_required
def api_reject_order(order_id):
    try:
        order = reject_order(order_id, rejected_by=session["user_id"])
        return jsonify({"ok": True, "order": order})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/team")
@broad_view_required
def api_team():
    role = session.get("role")
    region = REGION_HEAD_ROLES.get(role) if role != ADMIN_ROLE else None
    try:
        team = list_team(region=region)
        return jsonify({"team": team})
    except Exception as e:
        return jsonify({"team": [], "error": str(e)}), 200


@app.route("/api/team", methods=["POST"])
@admin_required
def api_create_team_member():
    body = request.get_json(force=True)
    try:
        member = create_team_member(body)
        return jsonify({"ok": True, "member": member})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/team/<int:staff_id>", methods=["PATCH"])
@admin_required
def api_update_team_member(staff_id):
    body = request.get_json(force=True)
    try:
        member = update_team_member(staff_id, body)
        return jsonify({"ok": True, "member": member})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/admin/sku-stock")
@admin_required
def api_sku_stock():
    try:
        return jsonify({"stock": list_sku_stock()})
    except Exception as e:
        return jsonify({"stock": [], "error": str(e)}), 200


@app.route("/api/admin/flavours")
@admin_required
def api_flavours():
    try:
        return jsonify({"flavours": list_flavours_admin(), "pack_formats": list_pack_formats()})
    except Exception as e:
        return jsonify({"flavours": [], "pack_formats": [], "error": str(e)}), 200


@app.route("/api/admin/flavours", methods=["POST"])
@admin_required
def api_create_flavour():
    body = request.get_json(force=True)
    try:
        flavour = create_flavour(body.get("name"), body.get("pack_format_ids") or [], created_by=session["user_id"])
        return jsonify({"ok": True, "flavour": flavour})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/admin/flavours/<int:flavour_id>", methods=["PATCH"])
@admin_required
def api_update_flavour(flavour_id):
    body = request.get_json(force=True)
    try:
        flavour = update_flavour(flavour_id, body)
        return jsonify({"ok": True, "flavour": flavour})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/admin/skus/<int:sku_id>/price", methods=["POST"])
@admin_required
def api_set_sku_price(sku_id):
    body = request.get_json(force=True)
    try:
        price = float(body.get("price"))
        row = set_sku_price(sku_id, price, set_by=session["user_id"])
        return jsonify({"ok": True, "price": row})
    except (ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": str(e) or "Invalid price"}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/admin/flavours/<int:flavour_id>/skus", methods=["POST"])
@admin_required
def api_add_sku(flavour_id):
    body = request.get_json(force=True)
    try:
        pack_format_id = int(body.get("pack_format_id"))
        sku = add_sku_to_flavour(flavour_id, pack_format_id)
        return jsonify({"ok": True, "sku": sku})
    except (ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": str(e) or "Invalid pack format"}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/admin/skus/<int:sku_id>/status", methods=["POST"])
@admin_required
def api_set_sku_status(sku_id):
    body = request.get_json(force=True)
    try:
        sku = set_sku_status(sku_id, body.get("status"))
        return jsonify({"ok": True, "sku": sku})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/admin/clients/<int:client_id>", methods=["PATCH"])
@admin_required
def api_update_client(client_id):
    body = request.get_json(force=True)
    try:
        client = update_client(client_id, body)
        return jsonify({"ok": True, "client": client})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/admin/addresses/<int:address_id>", methods=["PATCH"])
@admin_required
def api_update_address(address_id):
    body = request.get_json(force=True)
    try:
        addr = update_address(address_id, body)
        return jsonify({"ok": True, "address": addr})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/admin/skus/<int:sku_id>/hsn-gst", methods=["POST"])
@admin_required
def api_set_sku_hsn_gst(sku_id):
    body = request.get_json(force=True)
    try:
        gst_rate = float(body.get("gst_rate"))
        sku = set_sku_hsn_gst(sku_id, body.get("hsn_code"), gst_rate)
        return jsonify({"ok": True, "sku": sku})
    except (ValueError, TypeError) as e:
        return jsonify({"ok": False, "error": str(e) or "Invalid HSN/GST"}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/dashboard/orders/<int:order_id>/invoice")
@broad_view_required
def api_order_invoice(order_id):
    try:
        buf, filename = build_invoice_pdf(order_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return send_file(buf, mimetype="application/pdf", as_attachment=True, download_name=filename)


if __name__ == "__main__":
    app.run(debug=True, port=5001, threaded=True)
