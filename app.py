import os
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

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
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

PUBLIC_ENDPOINTS = {"login", "static"}
HEAD_OF_SALES_ROLE = "manager"


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


def head_of_sales_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != HEAD_OF_SALES_ROLE:
            return jsonify({"error": "forbidden"}), 403
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
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
    except Exception:
        return redirect(url_for("login", error="Invalid email or password"))
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    return render_template("index.html", user_email=session.get("user_email"),
                            full_name=session.get("full_name"), role=session.get("role"),
                            is_head_of_sales=session.get("role") == HEAD_OF_SALES_ROLE)


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", user_email=session.get("user_email"),
                            full_name=session.get("full_name"), role=session.get("role"),
                            is_head_of_sales=session.get("role") == HEAD_OF_SALES_ROLE)


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


@app.route("/api/clients", methods=["POST"])
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


@app.route("/api/dashboard/orders/<int:order_id>/mark-paid", methods=["POST"])
@head_of_sales_required
def api_mark_paid(order_id):
    try:
        payment = mark_payment_received(order_id, received_by=session["user_id"])
        return jsonify({"ok": True, "payment": payment})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/team")
@head_of_sales_required
def api_team():
    try:
        team = list_team()
        return jsonify({"team": team})
    except Exception as e:
        return jsonify({"team": [], "error": str(e)}), 200


@app.route("/api/team", methods=["POST"])
@head_of_sales_required
def api_create_team_member():
    body = request.get_json(force=True)
    try:
        member = create_team_member(body)
        return jsonify({"ok": True, "member": member})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001, threaded=True)
