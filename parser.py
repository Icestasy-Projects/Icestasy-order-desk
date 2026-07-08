import os
import re
import json
from sku_data import FLAVOUR_ALIASES, FORMAT_ALIASES, ACTIVE_SKUS, MOCK_PRICES, FLAVOUR_NAMES, FORMAT_NAMES

PAYMENT_KEYWORDS = {"advance", "invoice", "credit"}

# ── Groq LLM extraction ──────────────────────────────────────────────────────

_GROQ_SYSTEM = """You are an order parser for Icestasy, a premium ice cream brand.
Extract order items, payment mode, and client name from the pasted message.

Available flavours (id: name):
{flavours}

Available formats (id: name):
{formats}

Return ONLY valid JSON, no markdown, no extra text:
{{
  "items": [{{"qty": <int>, "flavour_id": <int or null>, "format_id": <int or null>}}],
  "payment": "<advance|invoice|credit or null>",
  "client_hint": "<name or null>"
}}

Rules:
- Match flavours and formats even with typos, Hindi/Marathi words, or short names.
- If a flavour is clear but format is not mentioned, set format_id to null (will show options).
- If nothing in a line matches a flavour or format, skip it.
- qty defaults to 1 if not mentioned.
- payment is one of: advance, invoice, credit — null if not mentioned.
"""


def _groq_extract(text: str):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        import requests
        flavours = "\n".join(f"  {fid}: {fname}" for fid, fname in FLAVOUR_NAMES.items())
        formats = "\n".join(f"  {pfid}: {pfname}" for pfid, pfname in FORMAT_NAMES.items())
        prompt = _GROQ_SYSTEM.format(flavours=flavours, formats=formats)
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                "temperature": 0,
                "max_tokens": 512,
            },
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"[parser] Groq extraction failed: {e}")
        return None


# ── Keyword fallback ─────────────────────────────────────────────────────────

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


def _keyword_extract(text: str):
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    items = []
    payment = None
    client_hint = None

    for line in lines:
        lower = line.lower()

        if lower.startswith("client:") or lower.startswith("client "):
            client_hint = re.sub(r"^client[:\s]+", "", line, flags=re.IGNORECASE).strip()
            continue

        for pm in PAYMENT_KEYWORDS:
            if pm in lower.split():
                payment = pm
                break
        else:
            qty_match = re.search(r"\b(\d+)\b", lower)
            qty = int(qty_match.group(1)) if qty_match else 1
            flavour_id = _find_flavour(lower)
            format_id = _find_format(lower)
            # A leading quantity is a strong signal this is an item line even when no
            # flavour alias hit directly — e.g. "5 Mango" now genuinely matches 3
            # different flavours, so it can't resolve via the single-id alias path,
            # but it's still clearly an item line, not a client name.
            has_leading_qty = re.match(r"^\d+\b", lower) is not None
            if flavour_id is None and format_id is None and not has_leading_qty:
                # Not an item line — treat as a client name if we don't have one yet
                if client_hint is None and line.strip():
                    client_hint = line.strip()
                continue
            # Extract hint words for fuzzy matching when flavour not found
            flavour_hint = None
            if flavour_id is None:
                stop = set(FORMAT_ALIASES.keys()) | {"and", "or", "the", "of"}
                hint_words = [w for w in lower.split() if not w.isdigit() and w not in stop]
                flavour_hint = " ".join(hint_words) if hint_words else None
            items.append({"qty": qty, "flavour_id": flavour_id, "format_id": format_id, "flavour_hint": flavour_hint})

    return {"items": items, "payment": payment, "client_hint": client_hint}


# ── SKU matching ─────────────────────────────────────────────────────────────

def _match_skus(flavour_id, format_id):
    return [
        s for s in ACTIVE_SKUS
        if (flavour_id is None or s["flavour_id"] == flavour_id)
        and (format_id is None or s["pack_format_id"] == format_id)
    ]


def _match_skus_fuzzy(hint: str, format_id):
    h = hint.lower()
    words = [w for w in h.split() if len(w) > 2]
    # Forward: hint words appear in flavour name
    results = [s for s in ACTIVE_SKUS
               if (format_id is None or s["pack_format_id"] == format_id)
               and any(w in s["flavour_name"].lower() for w in words)]
    if results:
        return results
    # Reverse: flavour name words appear in hint
    return [s for s in ACTIVE_SKUS
            if (format_id is None or s["pack_format_id"] == format_id)
            and any(w.lower() in h for w in s["flavour_name"].split() if len(w) > 2)]


def _get_sibling_skus(flavour_id: int, format_id):
    """Return all SKUs in the same flavour family (e.g. Belgian Speculoos + Belgian Chocolate).

    Matches on the flavour's *first* word only, not any shared word — with 53 flavours,
    matching any shared word >3 chars would wrongly group e.g. "Ratnagiri Hapoos (Mango)"
    with "Mango Mania" and "Mango Basil" just because they all contain "Mango".
    """
    our_name = FLAVOUR_NAMES.get(flavour_id, "")
    our_words = our_name.split()
    if not our_words or len(our_words[0]) <= 3:
        return []
    our_first = our_words[0].lower()
    sibling_ids = {flavour_id}
    for fid, fname in FLAVOUR_NAMES.items():
        if fid == flavour_id:
            continue
        other_words = fname.split()
        if other_words and other_words[0].lower() == our_first:
            sibling_ids.add(fid)
    if len(sibling_ids) == 1:
        return []  # no siblings found
    return [s for s in ACTIVE_SKUS
            if s["flavour_id"] in sibling_ids
            and (format_id is None or s["pack_format_id"] == format_id)]


def _get_price(sku):
    try:
        from order_engine import get_sku_price
        return get_sku_price(sku["id"], sku["pack_format_id"])
    except Exception:
        return MOCK_PRICES.get(sku["pack_format_id"], 0.0)


def _enrich(raw_items):
    result = []
    for item in raw_items:
        flavour_id = item.get("flavour_id")
        format_id = item.get("format_id")
        flavour_hint = item.get("flavour_hint")
        # When flavour wasn't identified but a hint exists, prefer fuzzy match
        # over _match_skus(None, ...) which returns every SKU in the format
        if flavour_id is None and flavour_hint:
            candidates = _match_skus_fuzzy(flavour_hint, format_id)
            if not candidates and format_id is not None:
                # No fuzzy hit but we do know the format — show every flavour in
                # that format as options. If format is *also* unknown, there's
                # nothing to narrow down from — that would return every active
                # SKU in the catalog, so leave it not-found instead.
                candidates = _match_skus(flavour_id, format_id)
        else:
            candidates = _match_skus(flavour_id, format_id)
        # Expand to sibling flavours (e.g. "Belgian" → Speculoos + Chocolate)
        if candidates and flavour_id is not None:
            siblings = _get_sibling_skus(flavour_id, format_id)
            if len(siblings) > 1:
                candidates = siblings
        if not candidates:
            result.append({
                "qty": item.get("qty", 1),
                "flavour_id": item.get("flavour_id"),
                "format_id": item.get("format_id"),
                "candidates": [],
                "ambiguous": False,
                "resolved_sku": None,
                "unit_price": None,
                "not_found": True,
            })
            continue
        ambiguous = len(candidates) > 1 or flavour_id is None
        for c in candidates:
            c["unit_price"] = _get_price(c)
        result.append({
            "qty": item.get("qty", 1),
            "flavour_id": flavour_id,
            "format_id": format_id,
            "candidates": candidates,
            "ambiguous": ambiguous,
            "resolved_sku": candidates[0] if not ambiguous else None,
            "unit_price": candidates[0]["unit_price"] if not ambiguous else None,
            "not_found": False,
        })
    return result


# ── Public API ───────────────────────────────────────────────────────────────

def parse_order_text(text: str) -> dict:
    # Try Groq first, fall back to keyword matching
    extracted = _groq_extract(text)
    if not extracted:
        extracted = _keyword_extract(text)

    return {
        "items": _enrich(extracted.get("items", [])),
        "payment": extracted.get("payment"),
        "client_hint": extracted.get("client_hint"),
    }