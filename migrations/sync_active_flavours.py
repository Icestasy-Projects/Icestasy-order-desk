"""
One-time migration: set only the listed flavours as active, deactivate the rest.
Creates any flavours that don't exist yet (with 4 Ltrs SKU).

Run: python migrations/sync_active_flavours.py
Requires SUPABASE_URL and SUPABASE_SERVICE_KEY env vars.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from order_engine import _sb, list_flavours_admin, list_pack_formats, create_flavour

ACTIVE_FLAVOURS = [
    "Ratnagiri Haapoos",
    "Amrood",
    "Palaapazham",
    "Chikkamagaluru Kaaphi",
    "Karikku",
    "Belgian Speculoos",
    "Mysore Paak",
    "Ukadiche Modak",
    "Gulqand",
    "French Vanilla",
    "Cookie Dusk",
    "Salted Caramel",
    "Kaju Katli",
    "Banarasi Meetha Paan",
    "Pineapple",
    "Kaffir Lime Coconut",
    "Vanilla Vantage (FD)",
    "Dakshin Laddoo",
    "Chikoo",
    "Sunkissed Twilight",
    "Dakkhan Sitaphal",
    "Dates and Almonds",
    "Japanese Matcha",
    "Vegan Mango",
    "Banana Caramel",
    "Signature Mango (Aurum)",
]

TARGET_FORMAT_NAME = "4 Ltrs"


def run():
    sb = _sb()
    existing = list_flavours_admin()
    existing_by_name = {f["name"].strip().lower(): f for f in existing}
    active_set = {name.strip().lower() for name in ACTIVE_FLAVOURS}

    pack_formats = list_pack_formats()
    target_fmt = next((pf for pf in pack_formats if pf["name"] == TARGET_FORMAT_NAME), None)
    if not target_fmt:
        print(f"ERROR: pack format '{TARGET_FORMAT_NAME}' not found. Available: {[pf['name'] for pf in pack_formats]}")
        return

    created = 0
    activated = 0
    deactivated = 0

    # 1. Create any missing flavours
    for name in ACTIVE_FLAVOURS:
        key = name.strip().lower()
        if key not in existing_by_name:
            print(f"  CREATE  {name}")
            create_flavour(name, [target_fmt["id"]], created_by=1)
            created += 1

    # 2. Activate listed flavours that aren't already active
    for name in ACTIVE_FLAVOURS:
        key = name.strip().lower()
        f = existing_by_name.get(key)
        if f and f["status"] != "active":
            print(f"  ACTIVATE  {f['name']} (was {f['status']})")
            sb.schema("sales").from_("flavours").update({"status": "active"}).eq("id", f["id"]).execute()
            activated += 1

    # 3. Deactivate all flavours NOT in the list
    for f in existing:
        key = f["name"].strip().lower()
        if key not in active_set and f["status"] == "active":
            print(f"  DEACTIVATE  {f['name']}")
            sb.schema("sales").from_("flavours").update({"status": "inactive"}).eq("id", f["id"]).execute()
            deactivated += 1

    print(f"\nDone: {created} created, {activated} reactivated, {deactivated} deactivated")
    print(f"Total active flavours: {len(ACTIVE_FLAVOURS)}")


if __name__ == "__main__":
    run()
