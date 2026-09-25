# Icestasy Order Desk

> Internal B2B order management platform for Icestasy Projects Pvt. Ltd.
> Version **1.0.0**

## Overview

Flask web application that handles the full lifecycle of B2B ice cream orders — from pasting a WhatsApp message to generating GST-compliant tax invoices. Deployed as a serverless app on Vercel, backed by Supabase (PostgreSQL) for data and auth.

Serves six Indian regions (Mumbai, Pune, Bangalore, Hyderabad, Delhi, Rest of India) with region-specific pricing, role-scoped dashboards, and a parser that understands vernacular flavour names, common typos, and Hindi/Marathi shorthand.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask (Python 3.x) |
| Database | Supabase (PostgreSQL), `sales` schema |
| Auth | Supabase Auth (email/password) |
| API Layer | PostgREST via Supabase client, 1000-row page size |
| Hosting | Vercel (serverless, `@vercel/python`) |
| PDF Generation | ReportLab + qrcode (UPI QR codes) |
| Excel Exports | openpyxl |
| Order Parsing | Regex + difflib fuzzy matching + Groq LLM (Llama 3.3 70B) fallback |
| Google Sheets Sync | Google Apps Script (`SheetSync.gs`) |
| Frontend | Server-rendered Jinja2 templates (SPA-style dashboard) |

## Role Hierarchy

| Role | Scope | Key Permissions |
|---|---|---|
| `admin` | All regions | Full CRUD on orders, clients, team, flavours, stock; approve/reject orders; generate invoices; manage pricing |
| `mumbai_head` | Mumbai (incl. Thane, Navi Mumbai, Vasai-Virar) | View/manage regional orders and team; create stock requests |
| `pune_head` | Pune | Same as above for Pune region |
| `bangalore_head` | Bangalore | Same as above for Bangalore region |
| `hyderabad_head` | Hyderabad | Same as above for Hyderabad region |
| `delhi_head` | Delhi | Same as above for Delhi region |
| `roi_head` | Rest of India | Same as above for ROI region |
| `salesperson` | Own orders only | Create orders, view own orders, search clients |

Admin and all regional heads share `BROAD_VIEW_ROLES` — they see the dashboard tabs (orders, clients, team, insights, stock, flavours) scoped to their region.

## Features

- **Natural-language order parsing** — paste a WhatsApp/text message; regex + fuzzy matching resolves flavours/formats; Groq LLM fallback for ambiguous input
- **Regional pricing** — 6 price regions with fallback chain (city → ROI → mock catalog)
- **Auto-hold** — orders from clients with unpaid invoices past the 15th of the month are automatically held
- **Tax invoices** — GST-compliant PDF with CGST/SGST (intrastate) or IGST (interstate), HSN codes, Indian-numbering amount-in-words, UPI QR code
- **Excel reports** — orders, clients, flavour sales; filterable by month, city, client, salesperson, SKU
- **Stock management** — per-city stock tracking, regional heads submit requests, admin approves line-by-line
- **Team management** — admin creates accounts with one-time passwords, forced change on first login
- **Tally ERP sync** — `/api/tally/sales` endpoint with static API key auth for accounting integration
- **Google Sheets sync** — Apps Script syncs historical sales data from "Sales Paste 2026" spreadsheet into Supabase
- **Client dues tracking** — outstanding balance per client with drill-down to individual unpaid orders
- **Flavour catalog admin** — CRUD flavours, attach pack formats/SKUs, set per-region prices
- **Dashboard** — SPA-style tabs (orders, clients, team, insights, stock, flavours) with role-based visibility

## Key Flows

### Order Creation

```
WhatsApp message → parser.py (regex + fuzzy + Groq LLM)
  → Matched SKUs + quantities displayed for confirmation
  → User selects client + delivery address
  → order_engine.create_order() checks auto-hold, generates order number
  → Order saved to sales.orders + sales.order_lines
```

### Order Number Format

```
{CITY_CODE}{MM}/{FY}/{SEQ}
Example: MU09/26-27/0042 (Mumbai, September, FY 2026-27, sequence 42)
```

City codes: `MU` (Mumbai), `PU` (Pune), `BA` (Bangalore), `HY` (Hyderabad), `DL` (Delhi), `ROI` (Rest of India).

Sequence is atomic — `sales.next_order_seq()` uses `INSERT ... ON CONFLICT DO UPDATE` with a row lock to prevent collisions under concurrency.

### Invoice Generation

```
Approved order → invoicing.py
  → Determines intrastate (Maharashtra) vs interstate
  → CGST+SGST (intrastate) or IGST (interstate) at per-SKU GST rate
  → ReportLab builds A4 PDF: company block, consignee, HSN line items, totals, UPI QR
  → Client running balance (Dr/Cr ledger) printed on invoice
```

### Order Lifecycle

```
created → [auto-held] → approved → completed
                      → rejected
                      → cancelled
```

Payments can be recorded at any stage. Hold can be manually released by admin/head.

## Database Schema

All tables live in the `sales` schema.

| Table | Purpose |
|---|---|
| `users` | Team accounts (linked to Supabase Auth UIDs); role, city, email |
| `clients` | B2B customer companies; name, GSTIN, contact |
| `addresses` | Delivery addresses per client; city, state, PIN, landmark |
| `orders` | Order header; order_no, client, salesperson, status, payment_mode, hold flag |
| `order_lines` | Line items; SKU, quantity, unit price, amount |
| `payments` | Payment records against orders; amount, date, note |
| `flavours` | Flavour catalog; name, active flag |
| `pack_formats` | Pack types (4L Tub, 12 Square, 50ml Cup, etc.) |
| `skus` | Flavour × format combinations; HSN code, GST rate, active flag |
| `sku_prices` | Per-region pricing; one row per SKU × price region |
| `order_collateral` | Attachments/collateral linked to orders |
| `stock_requests` | Stock request header; requesting city, status, requested_by |
| `stock_request_lines` | Individual SKU lines within a stock request; requested/approved qty |
| `order_sequences` | Atomic counter per (city_code, FY) for order number generation |

### Key Relationships

```
clients 1──∞ addresses
clients 1──∞ orders
orders  1──∞ order_lines
orders  1──∞ payments
flavours 1──∞ skus (via flavour_id)
pack_formats 1──∞ skus (via format_id)
skus 1──∞ sku_prices (one per region)
skus 1──∞ order_lines (via sku_id)
stock_requests 1──∞ stock_request_lines
```

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | Yes | Flask session signing key (must be persistent across instances) |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase anon/public key (used for auth sign-in) |
| `SUPABASE_ANON_KEY` | Yes | Alias used in some paths; same as `SUPABASE_KEY` |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service-role key (bypasses RLS for admin operations) |
| `GROQ_API_KEY` | No | Groq API key for LLM-based order parsing fallback |
| `TALLY_API_KEY` | No | Static key for Tally ERP sync endpoint authentication |

## Local Development

```bash
# Clone
git clone https://github.com/icestasy-projects/icestasy-order-desk.git
cd icestasy-order-desk

# Create virtualenv
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (create a .env file)
cp .env.example .env  # then fill in values

# Run
flask run --debug
```

### Dependencies (`requirements.txt`)

```
flask
supabase
python-dotenv
requests
openpyxl
reportlab
qrcode[pil]
```

## Deployment

Deployed on **Vercel** using `@vercel/python` runtime.

**`vercel.json`** routes all requests to `app.py`:

```json
{
  "version": 2,
  "builds": [{ "src": "app.py", "use": "@vercel/python" }],
  "routes": [{ "src": "/(.*)", "dest": "app.py" }]
}
```

Environment variables are set in the Vercel project dashboard.

Heavy imports (`reportlab`, `openpyxl`, `qrcode`) are deferred to local imports inside route handlers to avoid penalizing cold-start time on every request.

## Project Structure

```
icestasy-order-desk/
├── app.py                  # Flask app, routes, auth decorators, dashboard tabs
├── order_engine.py         # Core business logic, Supabase queries, order CRUD
├── parser.py               # Order text parser (regex + fuzzy + Groq LLM)
├── invoicing.py            # Tax invoice PDF generation (ReportLab)
├── reports.py              # Excel export builders (openpyxl)
├── sku_data.py             # Flavour/format catalog, aliases, mock fallback data
├── test_parser_suite.py    # Parser unit tests (standalone, no network)
├── requirements.txt        # Python dependencies
├── vercel.json             # Vercel deployment config
├── migrations/
│   ├── add_order_number_sequence_table.sql   # Atomic order-number counter
│   ├── add_stock_requests.sql                # Stock request tables
│   ├── add_order_collateral.sql              # Order attachments table
│   ├── add_region_head_roles.sql             # Regional head role columns
│   ├── add_onboarding_role.sql               # Onboarding role migration
│   ├── add_must_change_password.sql          # Forced password change flag
│   ├── add_sku_hsn_code_and_gst_rate.sql     # HSN/GST columns on SKUs
│   └── sync_active_flavours.py               # Flavour sync script
├── scripts/
│   └── google-sheets-sync/
│       └── SheetSync.gs    # Google Apps Script for Sheets → Supabase sync
├── static/
│   ├── style.css           # Global styles
│   ├── logo1.jpeg          # Company logo (original)
│   └── logo1_trimmed.png   # Company logo (trimmed, used in invoices)
└── templates/
    ├── dashboard.html      # SPA-style dashboard (2600+ lines, all tabs)
    ├── index.html          # New order creation page (1200+ lines)
    ├── login.html          # Login form
    └── change_password.html # Forced password change form
```

## Key Patterns

| Pattern | Where | Detail |
|---|---|---|
| PostgREST pagination | `order_engine._fetch_all_pages()` | Pages through 1000-row PostgREST cap with `range(start, end)` |
| Atomic sequences | `sales.next_order_seq()` | `INSERT ... ON CONFLICT DO UPDATE` with row lock prevents duplicate order numbers |
| Deferred heavy imports | `app.py` route handlers | `reportlab`, `openpyxl`, `qrcode` imported locally to cut cold-start time |
| Fuzzy matching | `parser._fuzzy_flavour_ids()` | `difflib.get_close_matches()` at 0.8 cutoff catches typos without false positives |
| LLM fallback | `parser._groq_extract()` | Groq (Llama 3.3 70B) parses orders that regex+fuzzy can't resolve |
| Auto-hold logic | `order_engine.should_auto_hold()` | Blocks orders for clients with unpaid invoices past the 15th |
| Locality rollup | `order_engine._PLACE_TO_CITY` | 100+ localities mapped to macro cities for reporting and region scoping |
| Price region fallback | `order_engine.price_region_for_city()` | City → region mapping; unmapped cities fall back to ROI |
| GST split | `invoicing.py` | Maharashtra addresses get CGST+SGST; all others get IGST |
| Service-role bypass | `order_engine._sb()` | Uses `SUPABASE_SERVICE_KEY` to bypass RLS for admin-level operations |

## Status

| Area | Status |
|---|---|
| Order creation & parsing | Production |
| Dashboard (all tabs) | Production |
| Invoice PDF generation | Production |
| Excel reports | Production |
| Stock requests | Production |
| Team management | Production |
| Tally ERP sync | Production |
| Google Sheets sync | In development |
| Client dues tracking | Production |
| Flavour catalog admin | Production |
