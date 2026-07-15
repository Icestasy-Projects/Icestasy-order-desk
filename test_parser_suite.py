#!/usr/bin/env python3
"""
Automated accuracy suite for the order parser, run against the real 53-flavour,
6-format catalog. Standalone - no Flask/network needed (uses the same mock
fallback the app uses when Supabase isn't reachable, which is an exact mirror
of the real sales.skus/flavours/pack_formats data).

Usage:
    python3 test_parser_suite.py            # full report, one line per case
    python3 test_parser_suite.py --quiet     # only failures + summary

Exit code 0 if every case passes, 1 otherwise (usable in CI).
"""
import sys

from parser import parse_order_text
from sku_data import FLAVOUR_ALIASES, FORMAT_ALIASES, ACTIVE_SKUS, _FLAVOURS

QUIET = "--quiet" in sys.argv

# ── Test case registry ───────────────────────────────────────────────────────
# Each case: (case_id, category, input_text, assertions_dict)
# assertions_dict keys (all optional, only listed ones are checked):
#   item_count       - exact number of parsed items
#   not_found        - bool, checked against items[0]
#   flavour_in       - substring that must appear in items[0]'s resolved OR
#                       candidate flavour name(s) (weak "is it findable" check)
#   candidate_set     - exact set of flavour names expected among candidates
#                       (strong check, only used where ground truth is computed
#                       independently of the parser's own logic)
#   format_in        - substring expected in resolved_sku's pack_format_name
#   qty              - exact qty on items[0]
#   payment          - exact payment value (or None)
#   client_hint      - substring expected in client_hint (or None to require None)

cases = []
_next_id = [1]


def add(category, text, **assertions):
    cases.append((_next_id[0], category, text, assertions))
    _next_id[0] += 1


# ── A. Every real flavour name, typed exactly (53 cases) ────────────────────
# Weak invariant: must resolve (not_found=False) and the exact name must be
# reachable among the returned candidates. Doesn't assert ambiguous=False here
# because a few flavours (Belgian, Mango, Strawberry pairs) intentionally
# surface their sibling too - that's covered precisely in section C.
for fid, fname in sorted(_FLAVOURS.items()):
    add("A-exact-name", f"1 {fname}", not_found=False, flavour_in=fname)

# ── B. Every alias, typed as the sole item line ──────────────────────────────
_target_names = {fid: name for fid, name in _FLAVOURS.items()}
for alias, fid in FLAVOUR_ALIASES.items():
    add("B-alias", f"2 {alias}", not_found=False, flavour_in=_target_names[fid])

# ── C. Ambiguous generic terms — ground truth computed independently ────────
# (plain substring search over the real flavour-name strings, not derived
# from parser.py's own matching code)
def flavours_containing(word):
    return {name for name in _FLAVOURS.values() if word.lower() in name.lower()}


_collision_words = ["mango", "vanilla", "chocolate", "caramel", "kesar", "strawberry",
                     "coconut", "belgian", "avocado", "paak"]
for word in _collision_words:
    matches = flavours_containing(word)
    if len(matches) >= 2:
        add("C-ambiguous", f"1 {word}", not_found=False, candidate_set=matches)
    elif len(matches) == 1:
        add("C-unique-word", f"1 {word}", not_found=False, flavour_in=next(iter(matches)))

# ── D. Format detection across all 6 formats (skip sibling-pair flavours to
#      keep expectations unambiguous: Belgian x2, Mango x2, Strawberry x2) ──
_sibling_fids = {8, 9, 21, 44, 47, 49}
_by_format = {}
for s in ACTIVE_SKUS:
    if s["flavour_id"] in _sibling_fids:
        continue
    _by_format.setdefault(s["pack_format_id"], []).append(s)

_format_alias_by_id = {}
for alias, pfid in FORMAT_ALIASES.items():
    _format_alias_by_id.setdefault(pfid, alias)

for pfid, skus in sorted(_by_format.items()):
    alias = _format_alias_by_id[pfid]
    for s in skus[:3]:
        add("D-format", f"1 {s['flavour_name']} {alias}",
            not_found=False, format_in=s["pack_format_name"], flavour_in=s["flavour_name"])

# ── E. Quantity extraction ───────────────────────────────────────────────────
add("E-qty", "Kaju Katli", qty=1)  # no digit -> defaults to 1
add("E-qty", "1 Kaju Katli", qty=1)
add("E-qty", "5 Kaju Katli", qty=5)
add("E-qty", "12 Kaju Katli", qty=12)
add("E-qty", "100 Kaju Katli", qty=100)
add("E-qty", "7 Gulqand", qty=7)
add("E-qty", "23 Pineapple", qty=23)
add("E-qty", "9 Jambhul", qty=9)

# ── F. Payment mode detection ────────────────────────────────────────────────
add("F-payment", "2 Kaju Katli\nAdvance", payment="advance")
add("F-payment", "2 Kaju Katli\nInvoice", payment="invoice")
add("F-payment", "2 Kaju Katli\nCredit", payment="credit")
add("F-payment", "2 Kaju Katli\nADVANCE", payment="advance")
add("F-payment", "2 Kaju Katli\ninvoice", payment="invoice")
add("F-payment", "2 Kaju Katli", payment=None)

# ── G. Client hint detection ─────────────────────────────────────────────────
add("G-client", "2 Kaju Katli\nClient: Ocean View Cafe", client_hint="Ocean View Cafe")
add("G-client", "2 Kaju Katli\nClient Ocean View Cafe", client_hint="Ocean View Cafe")
add("G-client", "2 Kaju Katli\nclient:   Spaced Out Cafe", client_hint="Spaced Out Cafe")
add("G-client", "2 Kaju Katli\nCLIENT: Upper Case Cafe", client_hint="Upper Case Cafe")
add("G-client", "2 Kaju Katli", client_hint=None)
add("G-client", "2 Kaju Katli\nOcean Pearl Diner", client_hint="Ocean Pearl Diner")

# ── H. Realistic multi-item orders ───────────────────────────────────────────
add("H-multi", "2 Gajar Halwa\n3 Pineapple\n1 Jambhul\nInvoice\nClient: Ocean View Cafe",
    item_count=3, payment="invoice", client_hint="Ocean View Cafe")
add("H-multi", "5 Kaju Katli\n5 Gulab Jamun\nAdvance", item_count=2, payment="advance")
add("H-multi", "2 Chikoo\n4 Ramphal\n6 Dates and Almonds\n1 Wasabi Punch\nCredit\nClient: Test Cafe",
    item_count=4, payment="credit", client_hint="Test Cafe")
add("H-multi", "1 Signature Chocolate\n1 Midnight Mania\n1 Legal Overdose", item_count=3)
add("H-multi", "10 Hass Avocado\n10 Puranpoli\nAdvance\nClient: Dakshin Diners",
    item_count=2, payment="advance", client_hint="Dakshin Diners")

# ── I. Not-found / garbage input ─────────────────────────────────────────────
for garbage in ["5 Xyzabc Nonsense Flavour", "3 Qwerty Uiop", "1 Foobar Baz Quux",
                 "10 Random Made Up Thing", "2 Zzzznotreal", "4 Blahblahblah",
                 "6 Nothing Matches Here", "1 Completely Fake Product"]:
    add("I-not-found", garbage, not_found=True)

# ── J. Case-insensitivity & formatting robustness ────────────────────────────
add("J-format-robust", "1 KAJU KATLI", not_found=False, flavour_in="Kaju Katli")
add("J-format-robust", "1 kaju katli", not_found=False, flavour_in="Kaju Katli")
add("J-format-robust", "1 KaJu KaTlI", not_found=False, flavour_in="Kaju Katli")
add("J-format-robust", "  2   Gulqand  ", not_found=False, flavour_in="Gulqand")
add("J-format-robust", "2 Gulqand\n\n\nAdvance", payment="advance")
add("J-format-robust", "1 PINEAPPLE\nINVOICE\nCLIENT: TEST", payment="invoice", client_hint="TEST")
add("J-format-robust", "\n\n2 Ramphal\n\n", not_found=False, flavour_in="Ramphal")
add("J-format-robust", "1 Jambhul\t\t", not_found=False, flavour_in="Jambhul")
add("J-format-robust", "1 dakshin laddoo", not_found=False, flavour_in="Dakshin Laddoo")
add("J-format-robust", "1 LEGAL OVERDOSE", not_found=False, flavour_in="Legal Overdose")

# ── K. Real, independently-sourced WhatsApp order messages ──────────────────
# Unlike A-J (derived from the parser's own alias/catalog data), these 9 are
# real messy human-typed messages the user pasted in. Ground truth for the
# genuinely ambiguous spots (S/M/G shorthand, "box" meaning, "Gova" typo) was
# confirmed by the user directly rather than guessed. Kept here permanently so
# future parser changes get regression-tested against real input, not just
# synthetic cases built from the same data the parser matches against.

add("K-real", "Louts biscoff 02 \nBelgium chocolate 01 \n(Veg treat express chikuwadi)",
    item_count=2, client_hint="chikuwadi")
add("K-real", "Kaju 1 Sheer korma 2 Guluqud 1",
    item_count=3)
add("K-real", "Gova =1 \n3 boxes modak icecream \nGoaikars coastal express pe chahiye",
    item_count=2, client_hint="Goaikars")
add("K-real", "1. Filter kaafi ice cream=1 box \n2. ⁠modak ice cream=1 box\n3. ⁠puranpoli ice cream=1 box",
    item_count=3)
add("K-real", "The food studio malad \nBelgium specloss =01",
    item_count=1, client_hint="food studio")
add("K-real", "Sudama Wakad 4 ltr Peruo Oro cholaclate Each 1 \nFor Soam 1 Bulk Jackfruit 1 Bulk kafir lime 1 Bulk Choclate",
    item_count=4)
add("K-real", " *Mi hi koli dombivli requirement* Modak icecream 1 Chocolate ice-cream 1 Vanila 1 Tender coconut 1",
    item_count=4)
add("K-real", "S-2 M-2 G-2",
    item_count=3)
add("K-real", "Send 1 biscoff ice cream Ratnagiri 2 Chocolate 1",
    item_count=3)
add("K-real", "4 ltr Happy Cloud-\n* Vanilla ice cream - 01 bulk\n* Strawberry - 01 bulk",
    item_count=2, client_hint=None)


def _run_k_quantity_checks():
    """K-real cases mix items that resolve unambiguously with items that stay
    ambiguous by design (generic words like "chocolate" deliberately aren't
    auto-resolved) — check per-item qty precisely here rather than cluttering
    the declarative `add()` table above with a mix of assertion shapes."""
    reasons = []
    expectations = {
        0: [2, 1],
        1: [1, 2, 1],
        2: [1, 3],
        3: [1, 1, 1],
        4: [1],
        5: [1, 1, 1, 1],
        6: [1, 1, 1, 1],
        7: [2, 2, 2],
        8: [1, 2, 1],
        9: [1, 1],
    }
    k_cases = [c for c in cases if c[1] == "K-real"]
    for idx, (case_id, category, text, assertions) in enumerate(k_cases):
        result = parse_order_text(text)
        got = [item["qty"] for item in result["items"]]
        expected = expectations.get(idx)
        if expected is not None and got != expected:
            reasons.append(f"K-real #{case_id} qty mismatch: expected {expected}, got {got}")
    return reasons


# ── Runner ────────────────────────────────────────────────────────────────────
def run_case(case_id, category, text, assertions):
    reasons = []
    try:
        result = parse_order_text(text)
    except Exception as e:
        return False, [f"raised exception: {e!r}"]

    items = result.get("items", [])

    if "item_count" in assertions and len(items) != assertions["item_count"]:
        reasons.append(f"item_count: expected {assertions['item_count']}, got {len(items)}")

    if "payment" in assertions and result.get("payment") != assertions["payment"]:
        reasons.append(f"payment: expected {assertions['payment']!r}, got {result.get('payment')!r}")

    if "client_hint" in assertions:
        expected = assertions["client_hint"]
        actual = result.get("client_hint")
        if expected is None:
            if actual is not None:
                reasons.append(f"client_hint: expected None, got {actual!r}")
        else:
            if not actual or expected.lower() not in actual.lower():
                reasons.append(f"client_hint: expected to contain {expected!r}, got {actual!r}")

    needs_item = any(k in assertions for k in
                      ("not_found", "flavour_in", "candidate_set", "format_in", "qty"))
    if needs_item:
        if not items:
            reasons.append("expected at least one item, got none")
        else:
            item = items[0]
            if "not_found" in assertions and item["not_found"] != assertions["not_found"]:
                reasons.append(f"not_found: expected {assertions['not_found']}, got {item['not_found']}")

            if "qty" in assertions and item["qty"] != assertions["qty"]:
                reasons.append(f"qty: expected {assertions['qty']}, got {item['qty']}")

            if "flavour_in" in assertions and not item["not_found"]:
                names = [c["flavour_name"] for c in item["candidates"]]
                if item.get("resolved_sku"):
                    names.append(item["resolved_sku"]["flavour_name"])
                target = assertions["flavour_in"]
                if not any(target.lower() == n.lower() for n in names):
                    reasons.append(f"flavour_in: {target!r} not found among candidates {names}")

            if "candidate_set" in assertions and not item["not_found"]:
                got = {c["flavour_name"] for c in item["candidates"]}
                expected = assertions["candidate_set"]
                if got != expected:
                    reasons.append(f"candidate_set: expected {sorted(expected)}, got {sorted(got)}")

            if "format_in" in assertions:
                resolved = item.get("resolved_sku")
                if not resolved:
                    reasons.append(f"format_in: expected {assertions['format_in']!r} but item is ambiguous/unresolved")
                elif assertions["format_in"].lower() not in resolved["pack_format_name"].lower():
                    reasons.append(f"format_in: expected {assertions['format_in']!r}, got {resolved['pack_format_name']!r}")

    return len(reasons) == 0, reasons


def main():
    passed = 0
    failed = 0
    by_category = {}

    for case_id, category, text, assertions in cases:
        ok, reasons = run_case(case_id, category, text, assertions)
        by_category.setdefault(category, [0, 0])
        by_category[category][0 if ok else 1] += 1

        if ok:
            passed += 1
            if not QUIET:
                print(f"PASS  #{case_id:<4} [{category}] {text!r}")
        else:
            failed += 1
            print(f"FAIL  #{case_id:<4} [{category}] {text!r}")
            for r in reasons:
                print(f"        - {r}")

    k_reasons = _run_k_quantity_checks()
    by_category.setdefault("K-real-qty", [0, 0])
    if k_reasons:
        failed += 1
        by_category["K-real-qty"][1] += 1
        print("FAIL  [K-real-qty] per-item quantities across the 9 real messages")
        for r in k_reasons:
            print(f"        - {r}")
    else:
        passed += 1
        by_category["K-real-qty"][0] += 1
        if not QUIET:
            print("PASS  [K-real-qty] per-item quantities across the 9 real messages")

    total = passed + failed
    accuracy = (passed / total * 100) if total else 0.0

    print("\n" + "=" * 70)
    print("PER-CATEGORY RESULTS")
    print("=" * 70)
    for cat, (p, f) in sorted(by_category.items()):
        t = p + f
        print(f"  {cat:<20} {p:>3}/{t:<3}  ({p/t*100:5.1f}%)")

    print("\n" + "=" * 70)
    print(f"TOTAL: {passed}/{total} passed  —  ACCURACY: {accuracy:.2f}%")
    print("=" * 70)

    if accuracy < 100.0:
        print(f"\n{failed} case(s) failed — see FAIL lines above for details.")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
