"""
Auto-submit order data to Google Forms (Pune B2B / Mumbai B2B).

Each order line is submitted as a separate form response so it appears
as one row in the linked spreadsheet — mirroring how manual form entries work.

Submission is fire-and-forget: failures are logged but never block the order.
"""

import logging
import threading
import urllib.request
import urllib.parse

log = logging.getLogger(__name__)

# ── Google Form IDs (the /formResponse endpoint) ────────────────────────────

MUMBAI_FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSeAqKm64RVhz5j3y5ZcIqMEZV6oVs9ts4D8wemEdbn294T0yQ/formResponse"
)
PUNE_FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLScWlQAS-stZ_BKN7Vfy-xu-snkqmgUhf-i6tjwV0O31laqHsg/formResponse"
)

# ── Field entry IDs ─────────────────────────────────────────────────────────

MUMBAI_FIELDS = {
    "client_type":   "entry.1444208573",
    "client_name":   "entry.1223009199",
    "contact_name":  "entry.1596957504",
    "area":          "entry.1804478374",
    "flavour":       "entry.135267378",
    "pack_format":   "entry.1984758189",
    "quantity":      "entry.810155099",
}

PUNE_FIELDS = {
    "client_type":   "entry.2077720335",
    "client_name":   "entry.196704870",
    "contact_name":  "entry.359276599",
    "area":          "entry.845920770",
    "flavour":       "entry.1593133959",
    "pack_format":   "entry.287623321",
    "quantity":      "entry.2001148330",
}

CITY_FORM_CONFIG = {
    "mumbai":    {"url": MUMBAI_FORM_URL, "fields": MUMBAI_FIELDS},
    "pune":      {"url": PUNE_FORM_URL,   "fields": PUNE_FIELDS},
}

# Mumbai Metropolitan Region cities all map to "mumbai"
MMR_CITIES = {"Mumbai", "Vasai-Virar", "Thane", "Navi Mumbai"}


def _city_key(city: str) -> str:
    if not city:
        return ""
    city = city.strip()
    if city in MMR_CITIES:
        return "mumbai"
    return city.lower()


def _submit_form(url: str, data: dict):
    """POST url-encoded form data to a Google Form. Best-effort."""
    try:
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=encoded, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info("Google Form submit OK (%s): %s", resp.status, url[:80])
    except Exception as e:
        log.warning("Google Form submit failed: %s", e)


def submit_order_to_google_form(
    city: str,
    client_name: str,
    contact_name: str,
    area: str,
    lines: list,
    is_new_client: bool = False,
):
    """Submit order lines to the city's Google Form (fire-and-forget in background).

    `lines` is a list of dicts: [{flavour_name, format_name, quantity}, ...]
    Each line becomes a separate form submission.
    """
    key = _city_key(city)
    config = CITY_FORM_CONFIG.get(key)
    if not config:
        return

    url = config["url"]
    fields = config["fields"]
    client_type = "New Client" if is_new_client else "Existing Client"

    def _do_submit():
        for line in lines:
            data = {
                fields["client_type"]:  client_type,
                fields["client_name"]:  client_name or "",
                fields["contact_name"]: contact_name or "",
                fields["area"]:         area or "",
                fields["flavour"]:      line.get("flavour_name") or "",
                fields["pack_format"]:  line.get("format_name") or "",
                fields["quantity"]:     str(line.get("quantity") or ""),
            }
            _submit_form(url, data)

    thread = threading.Thread(target=_do_submit, daemon=True)
    thread.start()
