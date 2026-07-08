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
FLAVOUR_ALIASES = {
    "hapoos": 1, "alphonso": 1, "ratnagiri": 1,
    "amrood": 2, "peru": 2,
    "kathal": 3, "jackfruit": 3, "palapazham": 3,
    "karikku": 4, "nariyal": 4, "tender coconut": 4,
    "modak": 5, "ukadiche": 5,
    "kaaphi": 6, "kaapi": 6, "chikkamagaluru": 6,
    "mysore paak": 7, "mysore pak": 7,
    "speculoos": 8, "belgian speculoos": 8,
    "belgian chocolate": 9,
    "meetha paan": 10, "banarasi": 10,
    "kaju katli": 13, "kaju": 13,
    "gulqand": 16,
    "kuro goma": 17, "black sesame": 17,
    "kaffir lime": 19,
    "matcha": 20, "japanese matcha": 20,
    "packaging unit": 22, "packaging": 22,
    "kesar thandai": 23, "thandai": 23,
    "hass avocado": 24,
    "gulab jamun": 25,
    "puranpoli": 26,
    "hara pista": 27,
    "yorkshire butterscotch": 28,
    "sheer qhurma": 30, "sheer khurma": 30, "qhurma": 30,
    "aale paak": 31,
    "caramelized popcorn": 32,
    "banana caramel": 33,
    "midnight mania": 34,
    "chikoo": 36, "sapota": 36,
    "dates and almonds": 37,
    "ramphal": 38,
    "wasabi punch": 39,
    "kashmiri kesar": 40,
    "crumble & dough": 41, "crumble and dough": 41,
    "madagascar vanilla": 42,
    "gajar halwa": 43, "carrot halwa": 43,
    "cutting chai": 45, "chai biskoot": 45,
    "signature chocolate": 46, "cacaoir": 46,
    "mango mania": 47,
    "pineapple": 48,
    "mango basil": 49,
    "apple pie": 50,
    "jambhul": 51,
    "dakshin laddoo": 52,
    "legal overdose": 53,
}

FORMAT_ALIASES = {
    "4l": 1, "4 l": 1, "bulk": 1, "tub": 1, "four litre": 1,
    "12sq": 2, "12 sq": 2, "square": 2, "12 square": 2,
    "sample": 3, "samples": 3, "50ml": 3, "50 ml": 3,
    "extras": 4, "extra": 4,
    "b2b": 5, "b2b add-on": 5, "add-on": 5, "addon": 5,
    "500ml": 6, "500 ml": 6,
}

# Mirrors the real sales.skus / sales.flavours / sales.pack_formats data exactly,
# so behaviour is identical whether Supabase is reachable or not.
_FLAVOURS = {
    1: "Ratnagiri Hapoos (Mango)", 2: "Amrood (Guava/Peru)", 3: "Palapazham (Jackfruit)",
    4: "Karikku (Tender Coconut)", 5: "Ukadiche Modak", 6: "Chikkamagaluru Kaaphi",
    7: "Mysore Paak", 8: "Belgian Speculoos", 9: "Belgian Chocolate",
    10: "Banarasi Meetha Paan", 11: "Salted Caramel", 12: "Vanilla Vantage (FD)",
    13: "Kaju Katli", 14: "Sunkissed Twilight", 15: "French Vanilla",
    16: "Gulqand", 17: "Kuro Goma", 18: "Cookie Dusk",
    19: "Kaffir Lime Coconut", 20: "Japanese Matcha", 21: "Strawberry Cream",
    22: "Packaging Unit", 23: "Kesar Thandai", 24: "Hass Avocado",
    25: "Gulab Jamun", 26: "Puranpoli", 27: "Hara Pista",
    28: "Yorkshire Butterscotch", 29: "Chocolate Choice (FD)", 30: "Sheer Qhurma",
    31: "Aale Paak", 32: "Caramelized Popcorn", 33: "Banana Caramel",
    34: "Midnight Mania", 35: "Blueberry Blush (FD)", 36: "Chikoo",
    37: "Dates and Almonds", 38: "Ramphal", 39: "Wasabi Punch",
    40: "Kashmiri Kesar", 41: "Crumble & Dough", 42: "Madagascar Vanilla",
    43: "Gajar Halwa", 44: "Strawberry Strength (FD)", 45: "Cutting Chai Biskoot",
    46: "Signature Chocolate (Cacaoir)", 47: "Mango Mania (FD)", 48: "Pineapple",
    49: "Mango Basil", 50: "Apple Pie", 51: "Jambhul",
    52: "Dakshin Laddoo", 53: "Legal Overdose",
}
_FORMATS = {
    1: ("4L Bulk", False), 2: ("12 Square", False), 3: ("50 ml Samples", True),
    4: ("Extras", False), 5: ("B2B Add-On", False), 6: ("500ml", False),
}
# (sku_code, flavour_id, pack_format_id) — one row per real active SKU
_SKU_ROWS = [
    ("RAT-4L-1", 1, 1), ("RAT-12SQ-1", 1, 2), ("RAT-Samp-1", 1, 3),
    ("AMR-4L-2", 2, 1), ("AMR-12SQ-2", 2, 2), ("AMR-Samp-2", 2, 3),
    ("PAL-4L-3", 3, 1), ("PAL-12SQ-3", 3, 2), ("PAL-Samp-3", 3, 3),
    ("KAR-4L-4", 4, 1), ("KAR-12SQ-4", 4, 2), ("KAR-Samp-4", 4, 3),
    ("UKA-4L-5", 5, 1), ("UKA-12SQ-5", 5, 2), ("UKA-Samp-5", 5, 3),
    ("CHI-4L-6", 6, 1), ("CHI-12SQ-6", 6, 2), ("CHI-Samp-6", 6, 3), ("CH2-500ML-6", 6, 6),
    ("MYS-4L-7", 7, 1), ("MYS-12SQ-7", 7, 2), ("MYS-Samp-7", 7, 3),
    ("BEL-4L-8", 8, 1), ("BEL-12SQ-8", 8, 2), ("BEL-Samp-8", 8, 3),
    ("BELG-4L-9", 9, 1),
    ("BAN-4L-10", 10, 1), ("BA3-500ML-10", 10, 6),
    ("SAL-4L-11", 11, 1), ("SA2-12SQ-11", 11, 2),
    ("VAN-4L-12", 12, 1),
    ("KAJ-4L-13", 13, 1),
    ("SUN-4L-14", 14, 1),
    ("FRE-4L-15", 15, 1),
    ("GUL-4L-16", 16, 1), ("GU3-12SQ-16", 16, 2),
    ("KUR-4L-17", 17, 1), ("KU2-12SQ-17", 17, 2),
    ("COO-4L-18", 18, 1), ("CO2-12SQ-18", 18, 2),
    ("KAF-4L-19", 19, 1),
    ("JAP-4L-20", 20, 1), ("JA2-12SQ-20", 20, 2),
    ("STR-4L-21", 21, 1),
    ("PAC-EXTRA-22", 22, 4),
    ("KES-4L-23", 23, 1),
    ("HAS-4L-24", 24, 1),
    ("GU2-4L-25", 25, 1),
    ("PUR-4L-26", 26, 1),
    ("HAR-4L-27", 27, 1),
    ("YOR-4L-28", 28, 1),
    ("CHO-4L-29", 29, 1),
    ("SHE-4L-30", 30, 1),
    ("AAL-4L-31", 31, 1), ("AA2-12SQ-31", 31, 2),
    ("CAR-B2BAD-32", 32, 5),
    ("BA2-4L-33", 33, 1),
    ("MID-4L-34", 34, 1),
    ("BLU-4L-35", 35, 1),
    ("CHI-4L-36", 36, 1),
    ("DAT-4L-37", 37, 1),
    ("RAM-4L-38", 38, 1),
    ("WAS-12SQ-39", 39, 2),
    ("KAS-4L-40", 40, 1),
    ("CRU-4L-41", 41, 1),
    ("MAD-4L-42", 42, 1),
    ("GAJ-4L-43", 43, 1),
    ("ST2-4L-44", 44, 1),
    ("CUT-4L-45", 45, 1),
    ("SIG-4L-46", 46, 1),
    ("MAN-4L-47", 47, 1),
    ("PIN-4L-48", 48, 1),
    ("MA2-4L-49", 49, 1),
    ("APP-4L-50", 50, 1),
    ("JAM-4L-51", 51, 1),
    ("DAK-4L-52", 52, 1),
    ("LEG-4L-53", 53, 1),
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
