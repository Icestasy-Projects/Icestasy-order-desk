"""
Standalone SKU/format/flavour data — mirrors sales.skus via Supabase,
falls back to a full mock mirror of the real catalog if env vars not set.
"""
import os

# Only unambiguous vernacular/alternate names go here — anything that now
# matches more than one flavour (mango, vanilla, chocolate, caramel, kesar,
# strawberry, ...) is deliberately left out so fuzzy matching surfaces all
# the real candidates for the user to disambiguate, instead of silently
# picking one.
#
# Values are the flavour's canonical NAME (matched case-insensitively against
# whichever catalog is live), never a raw id — sales.flavours ids have been
# renumbered/reshuffled over time (e.g. Kesar Thandai moved from the old
# offline id 23 to live id 55, Kyoka Kuro Goma from 55 to live 17), so a
# hardcoded id silently stops matching the moment the two drift apart. Name
# lookup self-heals across any future renumbering.
FLAVOUR_ALIASES = {
    "hapoos": "Ratnagiri Hapoos (Mango)", "alphonso": "Ratnagiri Hapoos (Mango)", "ratnagiri": "Ratnagiri Hapoos (Mango)",
    "amrood": "Amrood (Guava/Peru)", "peru": "Amrood (Guava/Peru)", "gova": "Amrood (Guava/Peru)",  # common typo/mishearing of "guava"
    "kathal": "Palaapazham (Jackfruit)", "jackfruit": "Palaapazham (Jackfruit)", "palapazham": "Palaapazham (Jackfruit)",
    "karikku": "Karikku (Tender Coconut)", "nariyal": "Karikku (Tender Coconut)", "tender coconut": "Karikku (Tender Coconut)",
    "modak": "Ukadiche Modak", "ukadiche": "Ukadiche Modak",
    "kaaphi": "Chikkamagaluru Kaaphi", "kaapi": "Chikkamagaluru Kaaphi", "chikkamagaluru": "Chikkamagaluru Kaaphi",
    "filter kaafi": "Chikkamagaluru Kaaphi", "filter coffee": "Chikkamagaluru Kaaphi",
    "mysore paak": "Mysore Paak", "mysore pak": "Mysore Paak",
    "speculoos": "Belgian Speculoos", "belgian speculoos": "Belgian Speculoos", "biscoff": "Belgian Speculoos",
    "lotus": "Belgian Speculoos", "lotus biscoff": "Belgian Speculoos",
    "belgium speculoos": "Belgian Speculoos",  # common typo of "Belgian"
    "belgian chocolate": "Cookie Dusk", "belgium chocolate": "Cookie Dusk",  # no live "Belgian Chocolate" flavour; real orders under this label are Cookie Dusk
    "cookie dusk": "Cookie Dusk",
    "meetha paan": "Banarasi Meetha Paan", "banarasi": "Banarasi Meetha Paan",
    "kaju katli": "Kaju Katli", "kaju": "Kaju Katli",
    "gulqand": "Gulqand", "guluqud": "Gulqand",  # common typo/mishearing
    "kuro goma": "Kyoka Kuro Goma", "black sesame": "Kyoka Kuro Goma",
    "kaffir lime": "Kaffir Lime Coconut",
    "matcha": "Japanese Matcha", "japanese matcha": "Japanese Matcha",
    "kesar thandai": "Kesar Thandai", "thandai": "Kesar Thandai",
    "hass avocado": "Hass Avocado",
    "gulab jamun": "Gulab Jamun",
    "puranpoli": "Puranpoli",
    "hara pista": "Hara Pista",
    "yorkshire butterscotch": "Yorkshire Butterscotch",
    "sheer qhurma": "Sheer Qhurma", "sheer khurma": "Sheer Qhurma", "qhurma": "Sheer Qhurma",
    "sheer korma": "Sheer Qhurma", "korma": "Sheer Qhurma",
    "aale paak": "Aale Paak",
    "caramelized popcorn": "Caramelized Popcorn",
    "banana caramel": "Banana Caramel",
    "midnight mania": "Midnight Mania (Ultra Dark Chocolate)",
    "chikoo": "Chikoo", "sapota": "Chikoo",
    "dates and almonds": "Dates and Almonds",
    "ramphal": "Ramphal",
    "wasabi punch": "Wasabi Punch",
    "kashmiri kesar": "Kashmiri Kesar",
    "crumble & dough": "Crumble and Dough", "crumble and dough": "Crumble and Dough",
    "madagascar vanilla": "Madagascar Vanilla",
    "gajar halwa": "Gajar Halwa", "carrot halwa": "Gajar Halwa",
    "cutting chai": "Cutting Chai Biskoot", "chai biskoot": "Cutting Chai Biskoot",
    "signature chocolate": "Signature Chocolate (Cacaoir)", "cacaoir": "Signature Chocolate (Cacaoir)",
    "mango mania": "Mango Mania (FD)",
    "pineapple": "Pineapple",
    "mango basil": "Mango Basil",
    "apple pie": "Apple Pie",
    "jambhul": "Jambhul",
    "dakshin laddoo": "Dakshin Laddoo",
    "legal overdose": "Legal Overdose",
    "reshmi paan": "Reshmi Paan",
    "kyoka kuro goma": "Kyoka Kuro Goma",  # longer/more specific than "kuro goma" — must sort before it
    "shahi sevaiya": "Shahi Sevaiya",
}

FORMAT_ALIASES = {
    "4l": 1, "4 l": 1, "bulk": 1, "tub": 1, "four litre": 1,
    "ltr": 1, "litre": 1, "liter": 1, "box": 1, "boxes": 1,
    "12sq": 2, "12 sq": 2, "square": 2, "12 square": 2,
    "sample": 3, "samples": 3, "50ml": 3, "50 ml": 3,
    "extras": 4, "extra": 4,
    "b2b": 5, "b2b add-on": 5, "add-on": 5, "addon": 5,
    "500ml": 6, "500 ml": 6,
}

# Mirrors the real sales.skus / sales.flavours / sales.pack_formats data exactly
# (last refreshed 2026-08-28 against the live catalog), so behaviour is
# identical whether Supabase is reachable or not. Several flavours have moved
# id since this was first written (e.g. Kesar Thandai 23->55, Madagascar
# Vanilla 42->448) and a handful (Gulab Jamun, Sheer Qhurma, Banarasi Meetha
# Paan, Caramelized Popcorn, Dates and Almonds, Pineapple, Jambhul, Legal
# Overdose, Signature Chocolate (Cacaoir), Chocolate Choice (FD)) have been
# discontinued outright — this block is refreshed to match exactly rather
# than patched id-by-id, since FLAVOUR_ALIASES resolves by name (see below),
# not by these ids, so drift here only matters for the offline-fallback path.
_FLAVOURS = {
    1: "Ratnagiri Hapoos (Mango)", 2: "Amrood (Guava/Peru)", 3: "Palaapazham (Jackfruit)",
    4: "Karikku (Tender Coconut)", 5: "Ukadiche Modak", 6: "Chikkamagaluru Kaaphi",
    7: "Mysore Paak", 8: "Belgian Speculoos",
    11: "Salted Caramel", 12: "Vanilla Vantage (FD)",
    13: "Kaju Katli", 14: "Sunkissed Twilight", 15: "French Vanilla",
    16: "Gulqand", 17: "Kyoka Kuro Goma", 18: "Cookie Dusk",
    19: "Kaffir Lime Coconut",
    54: "Reshmi Paan", 55: "Kesar Thandai", 57: "Dakkhan Sitaphal (Custard Apple)",
    434: "FD Chocolate", 435: "Gud & Sauf", 436: "Aale Paak", 437: "Apple Pie",
    438: "Banana Caramel", 439: "Chikoo", 440: "Cutting Chai Biskoot",
    441: "Dakshin Laddoo", 442: "Gajar Halwa", 443: "Hara Pista",
    444: "Hass Avocado", 445: "Japanese Matcha", 446: "Kashmiri Kesar",
    447: "Khajoor", 448: "Madagascar Vanilla", 449: "Mango Basil",
    450: "Midnight Mania (Ultra Dark Chocolate)", 451: "Miso Caramel",
    452: "Naarali Bhaat", 453: "Puranpoli", 454: "Qubaani (Apricots)",
    455: "Ramphal", 456: "Shahi Sevaiya", 457: "Strawberry Cream",
    458: "Tilgul", 459: "Vegan Chocolate", 460: "Vegan Mango",
    461: "Wasabi Punch", 462: "Yorkshire Butterscotch",
    463: "Signature Strawberry (Rosaea)", 464: "Crumble and Dough",
    465: "Off Season Sitaphal", 466: "Strawberry Strength (FD)",
    467: "Mango Mania (FD)", 468: "Blueberry Blush (FD)",
}
_FORMATS = {
    1: ("4L Bulk", False), 2: ("12 Square", False), 3: ("50 ml Samples", True),
    6: ("500ml", False),
}
# (sku_code, flavour_id, pack_format_id) — one row per real active SKU
_SKU_ROWS = [
    ("RAT-4L-1", 1, 1), ("RAT-12S-1", 1, 2),
    ("AMR-4L-2", 2, 1), ("AMR-12S-2", 2, 2),
    ("PAL-4L-3", 3, 1), ("PAL-12S-3", 3, 2),
    ("KAR-4L-4", 4, 1), ("KAR-12S-4", 4, 2),
    ("UKA-4L-5", 5, 1), ("UKA-12S-5", 5, 2),
    ("CHI-4L-6", 6, 1), ("CHI-12S-6", 6, 2),
    ("MYS-4L-7", 7, 1), ("MYS-12S-7", 7, 2),
    ("BEL-4L-8", 8, 1),
    ("SAL-4L-11", 11, 1), ("SAL-12S-11", 11, 2),
    ("VAN-4L-12", 12, 1),
    ("KAJ-4L-13", 13, 1),
    ("SUN-4L-14", 14, 1),
    ("FRE-4L-15", 15, 1),
    ("GUL-4L-16", 16, 1), ("GUL-12S-16", 16, 2),
    ("KUR-4L-17", 17, 1),
    ("COO-4L-18", 18, 1), ("COO-12S-18", 18, 2),
    ("KAF-4L-19", 19, 1),
    ("RES-4L-54", 54, 1),
    ("KES-4L-55", 55, 1),
    ("DAK-4L-57", 57, 1), ("DAK-12S-57", 57, 2),
    ("FDC-4L-434", 434, 1),
    ("GUD-4L-435", 435, 1),
    ("AAL-4L-436", 436, 1),
    ("APP-4L-437", 437, 1),
    ("BAN-4L-438", 438, 1),
    ("CHI-4L-439", 439, 1),
    ("CUT-4L-440", 440, 1),
    ("DAK-4L-441", 441, 1),
    ("GAJ-4L-442", 442, 1),
    ("HAR-4L-443", 443, 1),
    ("HAS-4L-444", 444, 1),
    ("JAP-4L-445", 445, 1),
    ("KAS-4L-446", 446, 1),
    ("KHA-4L-447", 447, 1),
    ("MAD-4L-448", 448, 1),
    ("MAN-4L-449", 449, 1),
    ("MID-4L-450", 450, 1),
    ("MIS-4L-451", 451, 1),
    ("NAA-4L-452", 452, 1),
    ("PUR-4L-453", 453, 1),
    ("QUB-4L-454", 454, 1),
    ("RAM-4L-455", 455, 1),
    ("SHA-4L-456", 456, 1),
    ("STR-4L-457", 457, 1),
    ("TIL-4L-458", 458, 1),
    ("VEG-4L-459", 459, 1),
    ("VEG-4L-460", 460, 1),
    ("WAS-4L-461", 461, 1),
    ("YOR-4L-462", 462, 1),
    ("SIG-4L-463", 463, 1),
    ("CRU-4L-464", 464, 1),
    ("OFF-4L-465", 465, 1),
    ("STR-4L-466", 466, 1),
    ("MAN-4L-467", 467, 1),
    ("BLU-4L-468", 468, 1),
]

MOCK_SKUS = [
    {
        "id": idx, "sku_code": sku_code,
        "flavour_id": fid, "flavour_name": _FLAVOURS[fid],
        "pack_format_id": pfid, "pack_format_name": _FORMATS[pfid][0],
        "is_sample": _FORMATS[pfid][1],
    }
    for idx, (sku_code, fid, pfid) in enumerate(_SKU_ROWS, start=1)
]

MOCK_PRICES = {1: 850.0, 2: 480.0, 3: 0.0, 4: 50.0, 5: 300.0, 6: 150.0}
PAYMENT_MODES = ["advance", "invoice", "credit"]


def load_live_skus():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        client = create_client(url, key)
        result = (
            client.schema("sales").from_("skus")
            .select("id, sku_code, flavour_id, pack_format_id, flavours(name), pack_formats(name, is_sample)")
            .eq("status", "active")
            .execute()
        )
        skus = []
        for row in result.data:
            fn = row["flavours"]["name"] if row.get("flavours") else ""
            pf = row["pack_formats"]["name"] if row.get("pack_formats") else ""
            is_s = row["pack_formats"]["is_sample"] if row.get("pack_formats") else False
            skus.append({
                "id": row["id"], "sku_code": row["sku_code"],
                "flavour_id": row["flavour_id"], "flavour_name": fn,
                "pack_format_id": row["pack_format_id"], "pack_format_name": pf,
                "is_sample": is_s,
            })
        return skus if skus else None
    except Exception as e:
        print(f"[sku_data] live load failed: {e}")
        return None


_live = load_live_skus()
ACTIVE_SKUS = _live if _live else MOCK_SKUS

# Derived from whichever catalog is actually active, so this never drifts out of sync.
FLAVOUR_NAMES = {s["flavour_id"]: s["flavour_name"] for s in ACTIVE_SKUS}
FORMAT_NAMES = {s["pack_format_id"]: s["pack_format_name"] for s in ACTIVE_SKUS}

# name (lowercased) -> id, for resolving FLAVOUR_ALIASES against the active catalog.
FLAVOUR_ID_BY_NAME = {name.strip().lower(): fid for fid, name in FLAVOUR_NAMES.items()}
