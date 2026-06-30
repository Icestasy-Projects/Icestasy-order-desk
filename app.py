import os
from flask import Flask, render_template, request, jsonify

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from parser import parse_order_text
from order_engine import search_clients, get_client_addresses, addr_label, create_order, register_client

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


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
        )
        return jsonify({"ok": True, "order": order})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001, threaded=True)