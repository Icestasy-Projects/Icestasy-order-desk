import os
import re
import json
import difflib
from sku_data import FLAVOUR_ALIASES, FORMAT_ALIASES, ACTIVE_SKUS, MOCK_PRICES, FLAVOUR_NAMES, FORMAT_NAMES

PAYMENT_KEYWORDS = {"advance", "invoice", "credit"}

# Word -> set(flavour_id) index used for typo-tolerant fuzzy matching (below).
# Only words >3 chars are indexed, same threshold used elsewhere for "meaningful" words.
_FLAVOUR_WORD_INDEX = {}
for _fid, _fname in FLAVOUR_NAMES.items():
    for _w in re.findall(r"[a-z]+", _fname.lower()):
        if len(_w) > 3:
            _FLAVOUR_WORD_INDEX.setdefault(_w, set()).add(_fid)

# 0.8 is empirically tuned: high enough that "matches" (ratio 0.769 vs "matcha")
# doesn't false-positive, low enough to catch real typos like "choclate" (0.941
# vs "chocolate"), "kafir" (0.909 vs "kaffir"), "vanila" (0.923 vs "vanilla"),
# "specloss" (0.824 vs "speculoos"). Typos further off than that (e.g. "guluqud"
# vs "gulqand" at 0.714) are handled via explicit aliases instead.
_FUZZY_CUTOFF = 0.8


def _fuzzy_flavour_ids(word: str) -> set:
    if len(word) <= 3:
        return set()
    close = difflib.get_close_matches(word, _FLAVOUR_WORD_INDEX.keys(), n=3, cutoff=_FUZZY_CUTOFF)
    ids = set()
    for w in close:
        ids |= _FLAVOUR_WORD_INDEX[w]
    return ids

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

_ZERO_WIDTH_RE = re.compile(r"[​‌‍﻿]")
_LIST_MARKER_RE = re.compile(r"^\s*(?:\d+[.)]|[•\-\*])\s*")
_QTY_LITRE_RE = re.compile(r"\b(\d+)\s*(?:ltr|litre|liter|l)\b", re.IGNORECASE)
_STOP_WORDS = {"and", "or", "the", "of", "each", "for", "pls", "please", "send", "required", "requirement"}


def _clean_text(text: str) -> str:
    text = _ZERO_WIDTH_RE.sub("", text)
    return text.replace("*", "")  # WhatsApp bold markers


def _strip_list_marker(line: str) -> str:
    """Strip a leading list number/bullet (e.g. "2. ") so it can't be misread as qty."""
    return _LIST_MARKER_RE.sub("", line).strip()


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


def _has_flavour_signal(text: str) -> bool:
    """Cheap check: does this text plausibly name a real flavour? Used only to
    decide which side of a quantity number is the item name when a line packs
    multiple items together (either "Name qty" or "qty Name", sometimes mixed
    within the same line)."""
    t = text.lower().strip()
    if not t:
        return False
    if _find_flavour(t) is not None:
        return True
    words = [w for w in re.findall(r"[a-z]+", t) if len(w) > 2 and w not in _STOP_WORDS]
    if not words:
        return False
    for fname in FLAVOUR_NAMES.values():
        fname_lower = fname.lower()
        fwords = {w for w in re.findall(r"[a-z]+", fname_lower) if len(w) > 2}
        if any(w in fname_lower for w in words) or (set(words) & fwords):
            return True
    # Tier 3: typo-tolerant fuzzy match (catches e.g. "Choclate", "Vanila", "kafir")
    if any(_fuzzy_flavour_ids(w) for w in words):
        return True
    return False


def _segment_line_items(line: str):
    """Split a line into (qty, item_text, extra_text) tuples, handling multiple
    items on one line with the quantity either before or after the item name
    (or mixed within the same line) — e.g. "Kaju 1 Sheer korma 2 Guluqud 1" or
    "1 Bulk Jackfruit 1 Bulk kafir lime". extra_text is the *other* side of the
    number, kept around only to sniff for a format word ("box"/"bulk"/...)
    that landed next to the item instead of inside its own claimed text.
    """
    # "S-2" -> "S 2": a hyphen between a letter and a digit is a separator here,
    # not part of a word — but leave letter-hyphen-letter alone (e.g. "add-on").
    line = re.sub(r"(?<=[A-Za-z])-(?=\d)", " ", line)
    tokens = re.split(r"(\d+)", line)
    segments = []
    claimed = set()
    i = 1
    while i < len(tokens):
        qty = int(tokens[i])
        preceding_idx, following_idx = i - 1, i + 1
        preceding_text = tokens[preceding_idx].strip() if preceding_idx not in claimed else ""
        following_text = tokens[following_idx].strip() if following_idx < len(tokens) else ""
        if preceding_text and _has_flavour_signal(preceding_text):
            segments.append((qty, preceding_text, following_text))
            claimed.add(preceding_idx)
        elif following_text and _has_flavour_signal(following_text):
            # This chunk (all text between two digits) can itself contain two
            # separate item names when a "Name qty" item is immediately followed
            # by a "Name qty" item with no digit of its own in between them, e.g.
            # "1 biscoff ice cream Ratnagiri 2" — "Ratnagiri" belongs to the *next*
            # digit, not this one. Try splitting off a trailing flavour-bearing
            # span and leave it unclaimed for the next digit's preceding-text pickup.
            words_chunk = following_text.split()
            split_done = False
            for split_point in range(len(words_chunk) - 1, 0, -1):
                head = " ".join(words_chunk[:split_point])
                tail = " ".join(words_chunk[split_point:])
                # Require a *strict* alias/name hit on both sides here (not the
                # looser word-overlap/fuzzy tiers _has_flavour_signal also allows) —
                # otherwise two words of the *same* flavour name (e.g. "Caramelized"
                # + "Popcorn") each weakly "signal" on their own and get wrongly
                # split into two items, silently dropping the tail (no next digit
                # to claim it).
                if _find_flavour(head.lower()) is not None and _find_flavour(tail.lower()) is not None:
                    segments.append((qty, head, preceding_text))
                    tokens[following_idx] = tail  # left for the next digit to claim
                    split_done = True
                    break
            if not split_done:
                segments.append((qty, following_text, preceding_text))
                claimed.add(following_idx)
        elif preceding_text and len(re.sub(r"[^a-zA-Z]", "", preceding_text)) <= 2:
            # Bare 1-2 letter shorthand code (e.g. "S-2") — no flavour signal
            # possible from the letter alone, but still worth a best-effort
            # match by initial letter later, rather than silently dropping it.
            segments.append((qty, preceding_text, following_text))
            claimed.add(preceding_idx)
        i += 2
    return segments


def _keyword_extract(text: str):
    text = _clean_text(text)
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    items = []
    payment = None
    client_hint = None

    for raw_line in lines:
        line = _strip_list_marker(raw_line)
        lower = line.lower()

        if lower.startswith("client:") or lower.startswith("client "):
            client_hint = re.sub(r"^client[:\s]+", "", line, flags=re.IGNORECASE).strip()
            continue

        matched_payment = False
        for pm in PAYMENT_KEYWORDS:
            if pm in lower.split():
                payment = pm
                matched_payment = True
                break
        if matched_payment:
            continue

        # "4 ltr"/"4 litre" describes the pack format, not an item quantity —
        # pull it out before segmenting so it doesn't get treated as an item's
        # qty (e.g. "4 ltr Peruo ... Each 1" is qty=1, format=4L Bulk, not qty=4).
        format_id_line = None
        litre_match = _QTY_LITRE_RE.search(line)
        if litre_match:
            format_id_line = 1
            line = _QTY_LITRE_RE.sub(" ", line, count=1)

        format_id_line = format_id_line or _find_format(lower)
        segments = _segment_line_items(line)

        if not segments and _has_flavour_signal(line):
            # No digit anywhere, but the line still names a real flavour
            # (e.g. plain "Kaju Katli") — one item, qty defaults to 1.
            segments = [(1, line, "")]

        if not segments:
            leading_digit = re.search(r"\d+", line)
            if leading_digit:
                # Has a quantity but nothing on the line looks like a real
                # flavour — still an item line (just one _enrich() will
                # correctly report as not-found), not a client name.
                segments = [(int(leading_digit.group()), line, "")]
            else:
                if client_hint is None and line.strip():
                    client_hint = line.strip()
                continue

        for qty, item_text, extra_text in segments:
            item_lower = item_text.lower()
            flavour_id = _find_flavour(item_lower)
            format_id = _find_format(item_lower) or _find_format(extra_text.lower()) or format_id_line
            flavour_hint = None
            if flavour_id is None:
                stop = set(FORMAT_ALIASES.keys()) | _STOP_WORDS
                hint_words = [w for w in re.findall(r"[a-z]+", item_lower) if w not in stop]
                flavour_hint = " ".join(hint_words) if hint_words else item_lower
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
    h = hint.lower().strip()
    words = [w for w in h.split() if len(w) > 2]
    # Forward: hint words appear in flavour name (substring, for typo/partial-word tolerance)
    results = [s for s in ACTIVE_SKUS
               if (format_id is None or s["pack_format_id"] == format_id)
               and any(w in s["flavour_name"].lower() for w in words)]
    if results:
        return results
    # Reverse: flavour name words appear as whole words in the hint. Must be a
    # whole-word match here (not "in h" substring-of-the-whole-string) - e.g.
    # "and" from "Dates and Almonds" is a substring of "random", which would
    # otherwise false-match any hint containing that word fragment.
    hint_words = set(words)
    results = [s for s in ACTIVE_SKUS
               if (format_id is None or s["pack_format_id"] == format_id)
               and any(w.lower() in hint_words for w in s["flavour_name"].split() if len(w) > 2)]
    if results:
        return results
    # Bare single-letter shorthand code (e.g. "S-2 M-2 G-2") — no reliable way
    # to know what it means, so match by the flavour name's first letter and
    # surface every candidate rather than silently guessing one.
    letters_only = re.sub(r"[^a-z]", "", h)
    if len(letters_only) == 1:
        return [s for s in ACTIVE_SKUS
                if (format_id is None or s["pack_format_id"] == format_id)
                and s["flavour_name"].lower().startswith(letters_only)]
    # Typo-tolerant fuzzy tier (e.g. "Choclate" -> Chocolate, "kafir" -> Kaffir)
    fuzzy_ids = set()
    for w in words:
        fuzzy_ids |= _fuzzy_flavour_ids(w)
    if fuzzy_ids:
        results = [s for s in ACTIVE_SKUS
                   if s["flavour_id"] in fuzzy_ids
                   and (format_id is None or s["pack_format_id"] == format_id)]
        if results:
            return results
    return []


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