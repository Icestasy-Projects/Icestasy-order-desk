import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from parser import parse_order_text
from order_engine import (
    search_clients, get_client_addresses, addr_label, create_order,
    register_client, create_address,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

PUBLIC_ENDPOINTS = {"login", "static"}


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
    if not session.get("user_email"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "unauthorized"}), 401
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=request.args.get("error"))

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    try:
        sb = _auth_client()
        result = sb.auth.sign_in_with_password({"email": email, "password": password})
        session["user_email"] = result.user.email
    except Exception:
        return redirect(url_for("login", error="Invalid email or password"))
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    return render_template("index.html", user_email=session.get("user_email"))


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
        client = register_client(body)
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
            billing_address_id=body.get("billing_address_id"),
            shipping_address_id=body.get("shipping_address_id"),
            notes=body.get("notes"),
            collateral=body.get("collateral"),
        )
        return jsonify({"ok": True, "order": order})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001, threaded=True)
