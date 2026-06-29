"""
Parse pasted order text into structured items, payment mode, and client hint.

Input example:
    2 Bulk Belgian
    3 Square Mango
    Advance
    Client: Trevor

Output:
    {
      "items": [{"qty": 2, "flavour_id": 8, "format_id": 1, "candidates": [...], "ambiguous": False}, ...],
      "payment": "advance" | None,
      "client_hint": "Trevor" | None,
    }
"""
import re
from sku_data import FLAVOUR_ALIASES, FORMAT_ALIASES, ACTIVE_SKUS, MOCK_PRICES, FLAVOUR_NAMES, FORMAT_NAMES

PAYMENT_KEYWORDS = {"advance", "invoice", "credit"}


def _find_flavour(text: str):
    for alias in sorted(FLAVOUR_ALIASES, key=len, reverse=True):
        if alias in text:
            return FLAVOUR_ALIASES[alias]
    return None


def _find_format(text: str):
    for alias in sorted(FORMAT_ALIASES, key=len, reverse=True):
        if alias in text:
            return FORMAT_ALIASES[alias]
    return None


def _match_skus(flavour_id, format_id):
    return [
        s for s in ACTIVE_SKUS
        if (flavour_id is None or s["flavour_id"] == flavour_id)
        and (format_id is None or s["pack_format_id"] == format_id)
    ]


def _get_price(sku):
    try:
        from order_engine import get_sku_price
        return get_sku_price(sku["id"], sku["pack_format_id"])
    except Exception:
        return MOCK_PRICES.get(sku["pack_format_id"], 0.0)


def parse_order_text(text: str) -> dict:
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    items = []
    payment = None
    client_hint = None

    for line in lines:
        lower = line.lower()

        # Client hint
        if lower.startswith("client:") or lower.startswith("client "):
            client_hint = re.sub(r"^client[:\s]+", "", line, flags=re.IGNORECASE).strip()
            continue

        # Payment mode
        for pm in PAYMENT_KEYWORDS:
            if pm in lower.split():
                payment = pm
                break
        else:
            # Try to detect item line: optional qty + flavour/format keywords
            qty_match = re.search(r"\b(\d+)\b", lower)
            qty = int(qty_match.group(1)) if qty_match else 1

            flavour_id = _find_flavour(lower)
            format_id = _find_format(lower)

            if flavour_id is None and format_id is None:
                continue  # not an item line

            candidates = _match_skus(flavour_id, format_id)
            if not candidates:
                continue

            ambiguous = len(candidates) > 1
            # Enrich candidates with price
            for c in candidates:
                c["unit_price"] = _get_price(c)

            items.append({
                "qty": qty,
                "flavour_id": flavour_id,
                "format_id": format_id,
                "candidates": candidates,
                "ambiguous": ambiguous,
                "resolved_sku": candidates[0] if not ambiguous else None,
                "unit_price": candidates[0]["unit_price"] if not ambiguous else None,
            })

    return {"items": items, "payment": payment, "client_hint": client_hint}

def _enrich(raw_items):
    result = []
    for item in raw_items:
        candidates = _match_skus(item.get("flavour_id"), item.get("format_id"))
        if not candidates:
            result.append({
                "qty": item.get("qty", 1),
                "flavour_id": item.get("flavour_id"),
                "format_id": item.get("format_id"),
                "candidates": [], "ambiguous": False,
                "resolved_sku": None, "unit_price": None, "not_found": True,
            })
            continue
        ambiguous = len(candidates) > 1
        for c in candidates:
            c["unit_price"] = _get_price(c)
        result.append({
            "qty": item.get("qty", 1),
            "flavour_id": item.get("flavour_id"),
            "format_id": item.get("format_id"),
            "candidates": candidates, "ambiguous": ambiguous,
            "resolved_sku": candidates[0] if not ambiguous else None,
            "unit_price": candidates[0]["unit_price"] if not ambiguous else None,
            "not_found": False,
        })
    return result