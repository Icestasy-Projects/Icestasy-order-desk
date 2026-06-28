"""
Standalone SKU/format/flavour data — mirrors production.skus via Supabase,
falls back to mock if env vars not set.
"""
import os

FLAVOUR_ALIASES = {
    "mango": 1, "hapoos": 1, "alphonso": 1, "ratnagiri": 1,
    "guava": 2, "peru": 2, "amrood": 2,
    "jackfruit": 3, "palapazham": 3, "kathal": 3,
    "coconut": 4, "tender coconut": 4, "karikku": 4, "nariyal": 4,
    "modak": 5, "ukadiche": 5,
    "coffee": 6, "kaaphi": 6, "kaapi": 6, "chikkamagaluru": 6,
    "mysore paak": 7, "mysore pak": 7, "mysore": 7,
    "speculoos": 8, "belgian": 8, "biscuit": 8,
}

FORMAT_ALIASES = {
    "4l": 1, "4 l": 1, "bulk": 1, "tub": 1, "four litre": 1,
    "12sq": 2, "12 sq": 2, "square": 2, "12 square": 2,
    "sample": 3, "50ml": 3, "samples": 3,
}

FLAVOUR_NAMES = {
    1: "Ratnagiri Hapoos Mango", 2: "Guava", 3: "Jackfruit",
    4: "Tender Coconut", 5: "Ukadiche Modak", 6: "Chikkamagaluru Kaaphi",
    7: "Mysore Paak", 8: "Belgian Speculoos",
}

FORMAT_NAMES = {1: "4L Bulk", 2: "12 Square", 3: "50ml Sample"}

MOCK_SKUS = []
_idx = 1
for fid, fname in FLAVOUR_NAMES.items():
    abbr = fname.split()[0][:3].upper()
    for pfid, pfname in FORMAT_NAMES.items():
        suffix = {1: "4L", 2: "12SQ", 3: "50ML"}[pfid]
        MOCK_SKUS.append({
            "id": _idx, "sku_code": f"{abbr}-{suffix}-{fid}",
            "flavour_id": fid, "flavour_name": fname,
            "pack_format_id": pfid, "pack_format_name": pfname,
            "is_sample": pfid == 3,
        })
        _idx += 1

MOCK_PRICES = {1: 850.0, 2: 480.0, 3: 0.0}
PAYMENT_MODES = ["advance", "invoice", "credit"]


def load_live_skus():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        client = create_client(url, key)
        result = (
            client.schema("production").from_("skus")
            .select("id, sku_code, flavour_id, pack_format_id, flavours(name), pack_formats(name, is_sample)")
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
        return skus
    except Exception as e:
        print(f"[sku_data] live load failed: {e}")
        return None


_live = load_live_skus()
ACTIVE_SKUS = _live if _live else MOCK_SKUS
