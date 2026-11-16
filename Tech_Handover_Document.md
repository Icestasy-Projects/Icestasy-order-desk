# Icestasy Order Desk

**Technical Handover Document**

*Prepared November 2026*

---

## System Overview

The Icestasy Order Desk is a B2B order management web application built for Icestasy Projects Pvt. Ltd. It handles the full order lifecycle for ice cream ingredient/premix sales: order intake (via WhatsApp text parsing or manual entry), client management, invoicing, payment tracking, MIS reporting, and stock management across Mumbai, Pune, and other cities.

### What the system does

- **Order creation** from pasted WhatsApp messages (AI-powered text parsing) or manual SKU selection
- **Client management** with billing/shipping addresses, GSTIN, dues tracking
- **Dashboard** with tabs: Orders, Clients, Team, Insights, Dues, Stock, Flavours, MIS
- **PDF invoicing** with GST (CGST/SGST or IGST), UPI QR code, running ledger
- **Excel exports** for Tally accounting integration, sales analysis, flavour reports
- **MIS reports** (daily, weekly, monthly sales summaries)
- **Stock management** with city-wise stock requests and factory FG stock view
- **Sample order workflow** with outcome tracking (converted/rejected/no response)
- **Google Sheets sync** (bidirectional) and Google Form integration
- **Tally API endpoint** for accounting software integration

---

## Architecture

### Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend | Python / Flask 3.1.1 | Single `app.py` entry point, serverless on Vercel |
| Database | Supabase (PostgreSQL) | Project: `acngdpcpxburkzqxjpbf`, all tables in `sales` schema |
| Auth | Supabase Auth | Email/password, JWT sessions mapped to `sales.users` |
| Frontend | Vanilla HTML/CSS/JS | Server-rendered Jinja2 templates, no build step |
| Hosting | Vercel | Deploys from `main` branch on GitHub |
| AI/LLM | Groq (llama-3.3-70b-versatile) | WhatsApp order text parsing, optional |
| PDF | ReportLab 4.2.5 | Invoice generation |
| Excel | openpyxl 3.1.5 | Report workbooks |
| QR Codes | qrcode[pil] 8.0 | UPI payment QR on invoices |

### File Structure

```
Icestasy-order-desk/
├── app.py                  # Flask app, all routes (~1181 lines)
├── order_engine.py         # Core business logic (~2425 lines)
├── parser.py               # WhatsApp text → structured order (~506 lines)
├── invoicing.py            # PDF invoice generation (~360 lines)
├── reports.py              # Excel workbook generation (~627 lines)
├── sku_data.py             # SKU catalog & fallback data (~260 lines)
├── google_form_sync.py     # Push orders to Google Forms (~115 lines)
├── requirements.txt        # Python dependencies
├── vercel.json             # Vercel routing config
├── templates/
│   ├── dashboard.html      # Main SPA dashboard (large)
│   ├── index.html          # Order creation form
│   ├── login.html          # Login page
│   ├── change_password.html
│   └── error.html
├── static/
│   ├── style.css
│   └── searchable-select.js
├── scripts/
│   ├── sync_orders.gs           # Tally sync Google Apps Script
│   └── google-sheets-sync/
│       └── SheetSync.gs         # Sheet sync with fuzzy matching
└── migrations/
    └── sync_active_flavours.py
```

### Request Flow

```
Browser → Vercel Edge → Python serverless function (app.py)
                                    ↓
                          Flask route handler
                                    ↓
                      order_engine.py (business logic)
                                    ↓
                  Supabase PostgreSQL (via supabase-py SDK)
                                    ↓
                      JSON response → Browser JS
```

> ℹ️ **Key architectural choice:** Heavy imports (ReportLab, Pillow, openpyxl) are deferred to local imports inside the routes that use them, not at module level. This dramatically reduces cold-start time for all other routes on Vercel's serverless platform.

---

## Deployment

### Vercel Configuration

All requests are routed to the Flask app via `vercel.json`:

```json
{
  "builds": [{ "src": "app.py", "use": "@vercel/python" }],
  "routes": [{ "src": "/(.*)", "dest": "app.py" }]
}
```

### Deployment Process

1. Push code to the `main` branch on GitHub
2. Vercel auto-deploys from `main`
3. Preview deployments created for pull requests
4. Environment variables configured in Vercel project settings

> ⚠️ **Important:** The `main` branch is the production branch. Never force-push to `main`. Always use pull requests for changes.

### GitHub Repository

Repository: `icestasy-projects/icestasy-order-desk` (private)

---

## Database Schema

### Supabase Project

- **Project ID:** `acngdpcpxburkzqxjpbf`
- **Dashboard:** supabase.com/dashboard/project/acngdpcpxburkzqxjpbf
- **Schema:** `sales` (all application tables)
- **Production schema:** `production` (factory stock views, managed separately)

### Core Tables

#### sales.users

Staff accounts linked to Supabase Auth via `auth_user_id`.

| Column | Type | Notes |
|--------|------|-------|
| id | bigint (identity) | PK, auto-generated |
| full_name | text | Display name |
| role | user_role enum | salesperson, admin, mumbai_head, pune_head, etc. |
| phone | text | Optional |
| email | text | Login email, matches Supabase Auth |
| is_active | boolean | Soft-delete flag |
| region | text | City assignment (Mumbai, Pune, etc.) |
| must_change_password | boolean | Forces password change on next login |
| auth_user_id | uuid | FK to Supabase `auth.users` |

#### sales.clients

B2B customers — HoReCa or distributors.

| Column | Type | Notes |
|--------|------|-------|
| id | bigint (identity) | PK |
| business_name | text | Company name |
| client_type | client_type enum | horeca / distributor |
| is_roi_dealer | boolean | Rest-of-India dealer flag (affects pricing) |
| gstin | text | GST registration number |
| primary_contact_phone | text | Required |
| city | text | Client's city |
| default_payment_mode | payment_mode enum | advance / invoice |
| status | client_status enum | active / inactive / blacklisted |
| registered_by | bigint | FK to users.id |

#### sales.orders

Commercial orders. `id` is `GENERATED ALWAYS` — never include in INSERTs.

| Column | Type | Notes |
|--------|------|-------|
| id | bigint (identity) | PK, auto-generated — DO NOT include in INSERT |
| order_no | text (UNIQUE) | Format: `MUM/26/11/0296` |
| client_id | integer | FK to clients |
| channel | text | whatsapp, portal, sales_assisted |
| order_type | text | commercial / sample |
| payment_mode | text | advance / invoice |
| status | text | draft → approved → invoiced → dispatched → delivered |
| salesperson_id | integer | FK to users |
| source | text | whatsapp_ai, manual, gform_import, gsheet_sync, sheet_sync, tally_import |
| subtotal_amount | numeric | Pre-tax, pre-discount |
| discount_amount | numeric | Total discount |
| tax_amount | numeric | GST amount |
| total_amount | numeric | Final invoice amount |

#### sales.order_lines

Line items for each order. Also `GENERATED ALWAYS` identity.

| Column | Type | Notes |
|--------|------|-------|
| id | bigint (identity) | PK — DO NOT include in INSERT |
| order_id | integer | FK to orders |
| sku_id | integer | FK to skus |
| quantity | numeric | Number of units |
| unit_price | numeric | Price per unit at time of order |
| line_discount_amount | numeric | Discount spread from header % |
| line_total | numeric | (qty x price) - discount |
| status | text | active / removed |

#### Other Key Tables

| Table | Purpose |
|-------|---------|
| addresses | Billing/shipping addresses per client, with GSTIN, state code, consignee |
| flavours | Flavour master list (name, status: active/inactive/discontinued) |
| pack_formats | Pack sizes: 4L Bulk, 12 Square, 50ml Samples, Extras, B2B Add-on, 500ml |
| skus | SKU = flavour + pack_format, has sku_code, HSN code, GST rate (default 5%) |
| sku_prices | Date-effective pricing per SKU per region (default, mumbai, pune, roi, etc.) |
| payments | Payment records: advance / balance / full, linked to order |
| sample_orders | Sample orders (separate table, mirrors orders structure) |
| sample_order_lines | Sample order line items |
| sample_outcomes | Track sample conversion: pending/converted/rejected/no_response |
| order_sequences | Atomic order number counter per city_code + FY |
| order_status_history | Audit trail of order status changes |
| order_collateral | Extra items (dry ice, spoons, etc.) attached to orders |
| order_links | Reorder/new order links for clients |
| discount_rules | Configurable discount rules (advance payment, ROI dealer, volume) |
| applied_discounts | Which rules were applied to which orders |
| stock_requests | City-wise stock requisitions from regional heads |
| stock_request_lines | Line items per stock request (requested_qty / approved_qty) |

### Database Functions (RPCs)

| Function | Returns | Purpose |
|----------|---------|---------|
| `next_order_seq(p_city_code, p_fy)` | integer | Atomic sequence for order numbers (INSERT...ON CONFLICT DO UPDATE) |
| `next_sample_order_seq()` | integer | Same for sample orders |
| `get_dashboard_orders()` | json | Aggregated order data with client/salesperson joins for dashboard |
| `get_sample_orders()` | json | Sample orders for dashboard |
| `normalize_order_no()` | trigger | BEFORE INSERT trigger — auto-converts old-format order numbers |
| `bulk_insert_orders_with_lines()` | jsonb | Batch order import |
| `import_orders()` | integer | Legacy import function |
| `get_fg_weekly_req()` | record | Factory finished goods weekly requirement |

### Trigger

`trg_normalize_order_no` — BEFORE INSERT on `sales.orders`. Detects old-format order numbers (e.g. `PU11/26-27/60`) and auto-converts them to the new uniform format (`PUN/26/11/0060`) by mapping 2-letter to 3-letter city codes and calling `next_order_seq`.

### Enum Types

| Type | Values |
|------|--------|
| user_role | salesperson, accounts, production, manager, admin, onboarding, mumbai_head, pune_head, bangalore_head, hyderabad_head, delhi_head, roi_head |
| order_status | draft, hold, pending_approval, approved, rejected, cancelled, invoiced, in_production, dispatched, delivered |
| client_type | horeca, distributor |
| client_status | active, inactive, blacklisted |
| payment_mode | advance, invoice |
| payment_type | advance, balance, full |
| payment_method | upi, bank_transfer, cheque, cash |
| sku_status | active, inactive, discontinued |
| sample_outcome | pending, converted, rejected, no_response |
| address_type | billing, shipping |

### Production Schema Views

The `production` schema is managed separately (not in this codebase) and exposes these views read by the app:

- `v_fg_stock` — Finished goods stock at factory (read by `_stock_rows_by_sku()`)
- `v_rm_stock` — Raw material stock
- `v_prep_stock` — Prep stock
- `v_stock_targets_fg`, `v_stock_targets_rm`, `v_stock_targets_prep` — Stock targets
- `v_stock_alerts_fg`, `v_stock_alerts_rm`, `v_stock_alerts_prep` — Stock alerts

### Row Level Security (RLS)

Most tables use `service_role_all` policies (the app backend uses the service role key). Some catalog tables (clients, flavours, pack_formats, skus, sku_prices, discount_rules, sample_outcomes) also allow `authenticated read` or `anon_select` for the Google Apps Scripts that use the anon key.

---

## Authentication & Roles

### Login Flow

1. User submits email + password to `POST /login`
2. App calls `sb.auth.sign_in_with_password()` against Supabase Auth
3. On success, looks up `sales.users` by email, checks `is_active`
4. Stores user_id, role, region, full_name in Flask server-side session
5. Session cookie: 30-day permanent, Secure, HttpOnly, SameSite=Lax
6. Session revalidated every 300 seconds (re-reads `sales.users` row)

### Three Authorization Decorators

| Decorator | Who gets access | Used for |
|-----------|----------------|----------|
| `@admin_required` | admin + all regional heads (`BROAD_VIEW_ROLES`) | Most admin/dashboard endpoints |
| `@broad_view_required` | Same as admin_required | Alias, used interchangeably |
| `@strict_admin_required` | Only `role == 'admin'` | Reset password, deactivate, delete team members |
| `@tally_api_key_required` | External systems with API key | `/api/tally/sales` endpoint |

### Role Hierarchy

```
admin                     → Full access, all cities, all actions
├── mumbai_head            → Mumbai region orders/team/stock
├── pune_head              → Pune region
├── bangalore_head         → Bangalore region
├── hyderabad_head         → Hyderabad region
├── delhi_head             → Delhi region
├── roi_head               → Rest of India
└── salesperson            → Own orders only, limited dashboard
    accounts, production,
    manager, onboarding    → Login access but limited features
```

### Jinja/JS Permission Flags

- `IS_ADMIN` (Jinja/JS) = `role in BROAD_VIEW_ROLES` — admin + heads see dashboard data
- `IS_STRICT_ADMIN` (JS only) = `role == 'admin'` — controls visibility of Reset Password / Deactivate / Delete buttons

### Regional Head Restrictions

The `_forbid_team_change()` function (app.py line 144) enforces:

- Heads can only create/edit **salesperson** accounts in **their own region**
- Heads cannot promote anyone to head/admin role
- Heads cannot reset passwords or delete staff in other regions
- Heads editing themselves cannot change their own role or region

---

## API Endpoints

### Pages (GET, return HTML)

| Route | Auth | Purpose |
|-------|------|---------|
| `/login` | Public | Login page (GET) and auth (POST) |
| `/logout` | Any | Clear session, redirect to login |
| `/change-password` | Any | Password change form |
| `/` | Any logged in | Dashboard (SPA) |
| `/new-order` | Any logged in | Order creation form |

### Order APIs

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/api/parse` | POST | Any | Parse WhatsApp text → structured items |
| `/api/parse/flavour-options` | GET | Any | All active SKUs with prices |
| `/api/reprice` | POST | Any | Recalculate prices for changed items |
| `/api/orders` | POST | Any | Create commercial order |
| `/api/sample-orders` | POST | Any | Create sample order |
| `/api/orders/stock-check` | POST | Any | Pre-order stock availability check |
| `/api/orders/<id>/cancel` | POST | Any | Cancel order |
| `/api/orders/<id>/put-on-hold` | POST | Admin | Put order on hold |
| `/api/orders/<id>/release-hold` | POST | Admin | Release hold |

### Dashboard APIs

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/dashboard/orders` | GET | List orders (filtered by role/region) |
| `/api/dashboard/export` | GET | Download Excel workbook |
| `/api/dashboard/export-sample-orders` | GET | Download sample orders Excel |
| `/api/dashboard/orders/<id>/lines` | GET | Order line items |
| `/api/dashboard/orders/<id>/complete` | POST | Mark order completed (admin) |
| `/api/dashboard/orders/<id>/mark-paid` | POST | Record payment |
| `/api/dashboard/orders/<id>/approve` | POST | Approve order (admin) |
| `/api/dashboard/orders/<id>/reject` | POST | Reject order (admin) |
| `/api/dashboard/orders/<id>/invoice` | GET | Download PDF invoice |
| `/api/dashboard/mis` | GET | MIS data (daily/weekly/monthly) |
| `/api/dashboard/flavour-sales` | GET | Flavour/SKU sales insights |

### Client APIs

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/clients/search` | GET | Search by name (typeahead) |
| `/api/clients` | GET | Paginated client list |
| `/api/clients/all-lite` | GET | Lightweight list for dropdowns |
| `/api/clients/export` | GET | Clients Excel |
| `/api/clients/dues` | GET | Client dues summary |
| `/api/clients/<id>/due-detail` | GET | Single client due breakdown |
| `/api/clients` | POST | Register new client |
| `/api/clients/<id>/addresses` | GET/POST | List / create addresses |
| `/api/admin/clients/<id>` | PATCH | Update client (admin) |
| `/api/admin/clients/<id>` | DELETE | Delete client (admin) |
| `/api/admin/clients/bulk-move` | POST | Bulk change client city |
| `/api/admin/clients/bulk-delete` | POST | Bulk delete clients |

### Team APIs

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/api/team` | GET | Admin | List staff |
| `/api/team` | POST | Admin | Create staff member + Supabase Auth account |
| `/api/team/<id>` | PATCH | Admin | Update staff member |
| `/api/team/<id>` | DELETE | Admin | Soft-delete (deactivate) |
| `/api/team/<id>/permanent` | DELETE | Strict Admin | Hard delete (fails if FK exists) |
| `/api/team/<id>/reset-password` | POST | Strict Admin | Generate temp password |

### SKU / Flavour / Stock APIs

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/skus` | GET | List active SKUs with prices |
| `/api/admin/sku-stock` | GET | Factory FG stock (admin) |
| `/api/city-stock` | GET | City-wise stock summary |
| `/api/stock-requests` | GET/POST | List / create stock requests |
| `/api/stock-requests/<id>/approve` | POST | Approve stock request (admin) |
| `/api/stock-requests/<id>/reject` | POST | Reject stock request (admin) |
| `/api/admin/flavours` | GET/POST | List / create flavours (admin) |
| `/api/admin/flavours/<id>` | PATCH | Update flavour (admin) |
| `/api/admin/flavours/bulk-delete` | POST | Discontinue flavours (admin) |
| `/api/admin/skus/<id>/price` | POST | Set SKU price with date-effective rows |
| `/api/admin/flavours/<id>/skus` | POST | Add SKU to flavour (admin) |
| `/api/admin/skus/<id>/status` | POST | Toggle SKU active/inactive |

### External / M2M APIs

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/api/tally/sales` | GET | API Key | Tally-formatted sales data with HSN, GST split |

---

## Order System

### Order Creation Flow

1. **Text Input:** User pastes WhatsApp order text
2. **Parsing:** Two-tier system — Groq LLM primary (llama-3.3-70b-versatile), keyword/fuzzy fallback if LLM fails
3. **Resolution:** Parsed items matched to SKUs via fuzzy matching (`difflib.get_close_matches` at 0.8 cutoff)
4. **Pricing:** Prices loaded from `sku_prices` with region fallback chain: specific region → "default" → "roi" → MOCK_PRICES
5. **Review:** User confirms/edits items, selects client, addresses
6. **Submission:** `create_order()` — atomic creation with rollback on failure
7. **Post-creation:** Order pushed to Google Form via `google_form_sync`

### Order Number Format

```
{3-letter CITY}/{YY}/{MM}/{SEQ:04d}
Examples: MUM/26/11/0296, PUN/26/11/0030, ROI/26/11/0001
```

City codes: MUM (Mumbai, Thane, Navi Mumbai, Vasai-Virar), PUN (Pune), BLR (Bangalore), HYD (Hyderabad), DEL (Delhi), ROI (rest of India).

Sequence generation is atomic via the `next_order_seq(p_city_code, p_fy)` RPC, which uses INSERT...ON CONFLICT DO UPDATE to prevent race conditions.

> ℹ️ **Old format migration:** A BEFORE INSERT trigger (`trg_normalize_order_no`) auto-converts old-format numbers (e.g. `PU11/26-27/60`) to the new format. Historical Tally imports retain their original format for audit trail preservation.

### Order Statuses

```
draft → hold (optional) → approved → invoiced → in_production → dispatched → delivered
  └→ rejected
  └→ cancelled
```

### Auto-Hold Logic

Orders from clients with existing pending (unpaid) orders are automatically put on hold. The `should_auto_hold()` function checks for pending orders from the same client.

### Pack Format Constraint

> ⚠️ **Business rule:** 500ml and 150ml pack formats are skipped when creating order lines. The `create_order()` function filters these out.

### Order Text Parser (parser.py)

- **Primary:** Groq LLM (`llama-3.3-70b-versatile`) extracts structured items from natural language
- **Fallback:** Keyword extraction with `_segment_line_items()` handles "Name qty" and "qty Name" patterns
- **Fuzzy matching:** `difflib.get_close_matches` at 0.8 cutoff for typo tolerance
- **Alias mapping:** Extensive alias dictionary in `sku_data.py` — Hindi/Marathi names, common misspellings
- **Ambiguous flavours:** Some names map to multiple SKUs (e.g. "Belgian" → Speculoos + Chocolate)
- **LLM output sanitization:** `_sanitize_extracted()` validates LLM output as untrusted data

### Discount System

Header-level percentage discount is spread across order lines via `order_discount_factor()`. Each line gets: `line_discount = unit_price x qty x (1 - factor)` where factor = `(subtotal - discount) / subtotal`.

---

## Pricing & SKUs

### SKU Structure

```
Flavour (e.g. "Belgian Chocolate")
  └→ SKU = Flavour + Pack Format (e.g. "Belgian Chocolate - 4L Bulk")
       └→ Price = per SKU, per region, date-effective
```

### Pack Formats

| ID | Name | Default Price (INR) |
|----|------|---------------------|
| 1 | 4L Bulk | 850 |
| 2 | 12 Square | 480 |
| 3 | 50ml Samples | 0 (free) |
| 4 | Extras | 50 |
| 5 | B2B Add-on | 300 |
| 6 | 500ml | 150 |

### Price Region Fallback

```
Client city → price_region_for_city() → specific region
  → if no price: try "default" region
  → if still none: try "roi" region
  → if still none: MOCK_PRICES (hardcoded by format_id)
```

### Date-Effective Pricing

When a new price is set via `set_sku_price()`, the previous price row's `effective_to` is set to yesterday, and a new row is created with `effective_from` = today. This preserves price history for reporting.

### SKU Data Loading

`sku_data.py` tries to load live SKU data from Supabase at import time. If Supabase is unavailable, it falls back to hardcoded `MOCK_SKUS` (~80 SKUs). This ensures the app can start even if the database is temporarily down.

---

## Integrations

### 1. Google Forms (Outbound)

File: `google_form_sync.py`

After every order is created in the web app, each order line is pushed as a separate Google Form response:

- **Mumbai form:** For orders in Mumbai, Vasai-Virar, Thane, Navi Mumbai
- **Pune form:** For all other cities

This mirrors the data into the master Google Sheets that the operations team uses for production planning.

### 2. Google Forms (Inbound — gform_import)

External Google Forms/Apps Script (NOT in this repo) creates orders directly in Supabase. These show `source = 'gform_import'`. The Pune form historically used old-format order numbers, now auto-converted by the trigger.

### 3. Tally Sync (sync_orders.gs)

File: `scripts/sync_orders.gs`

Google Apps Script that:

- Reads from the "Combined" sheet in the master Google Sheet
- Groups line items by Invoice number
- Upserts to Supabase via REST API (anon key)
- Filters: Mumbai/Pune only, existing clients only, rows after Sep 1, 2026
- Daily trigger at 10 PM IST
- Source: `gsheet_sync`

### 4. Sheet Sync (SheetSync.gs)

File: `scripts/google-sheets-sync/SheetSync.gs`

More sophisticated sync with:

- Fuzzy client matching (3-tier: exact → normalised core + location scoring → auto-create)
- Extensive `FLAVOUR_MAP` mapping Excel names to DB names
- `NO_SKU` set for discontinued/unmapped flavours (skipped silently)
- Resumable sync (stops 60s before GAS 6-min limit, auto-continues via trigger)
- Marks synced rows in column N of the sheet
- Uses service_role key (stored in ScriptProperties, not hardcoded)
- Source: `sheet_sync`

### 5. Tally API

`GET /api/tally/sales` — authenticated with `X-API-Key` header. Returns Tally-formatted sales data with:

- Voucher types: "Icecream Sale- Mumbai" / "Icecream Sale - Pune"
- HSN codes, GST rates
- CGST/SGST (intrastate) or IGST (interstate) split
- Used by Tally accounting software for automatic voucher creation

> ⚠️ **Interstate vs Intrastate:** Tax splitting uses `is_interstate_supply()` from order_engine.py. Intrastate (within Maharashtra) = CGST + SGST. Interstate = IGST. Based on shipping address state code.

---

## Stock Management

### Two Stock Systems

#### 1. Factory FG Stock (Central)

Read from `production.v_fg_stock` view (managed by separate production system). Shown on the dashboard Stock tab.

#### 2. City-wise Stock (Requisition/Dispatch)

Regional heads create `stock_requests` for their city. Admin approves (sets `approved_qty`) or rejects. City stock = total dispatched - total used (from order lines), excluding `historical_import` orders.

Cities with stock tracking: `STOCK_REQUEST_CITIES` = all cities from `REGION_HEAD_ROLES.values()`.

### Pre-Order Stock Check

`check_stock_for_order()` is called before order creation to warn if city stock is insufficient. It's advisory, not blocking.

---

## Invoicing & Reports

### PDF Invoices (invoicing.py)

- Generated on-demand via `GET /api/dashboard/orders/<id>/invoice`
- A4 layout using ReportLab
- Company: Icestasy Projects Pvt. Ltd., GSTIN 27AAECI1609N1ZE
- UPI: Icestasy@icici (QR code on invoice)
- Includes: consignee/buyer blocks, HSN-coded line items, CGST/SGST or IGST, running client balance
- `amount_in_words()`: Indian numbering system (crore/lakh)

### Excel Reports (reports.py)

Downloaded via `GET /api/dashboard/export` with a `type` parameter:

| Type | Content |
|------|---------|
| all | All orders, multi-sheet workbook with month tabs |
| month | Specific month orders |
| city | Orders filtered by city |
| client | Orders for a specific client |
| salesperson | Orders by salesperson |
| flavour | Flavour sales summary + detail |
| sku | SKU-level analysis |

Security: `_neutralize_formulas()` prevents formula injection by escaping cell values starting with "=".

### MIS Reports

- `mis_daily_sales()` — Today's sales aggregated by city
- `mis_weekly_sales()` — Current week, grouped by date
- `mis_monthly_sales()` — Current month, grouped by week

---

## Environment Variables

### Required — Set in Vercel Project Settings

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Flask session secret (MUST be persistent across deploys) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon/public key (used for auth login) |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (used for all data operations) |
| `TALLY_API_KEY` | API key for `/api/tally/sales` M2M endpoint |

### Optional

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Groq API key for LLM-based order parsing (falls back to keyword parser if missing) |
| `FLASK_DEBUG` | Enable Flask debug mode (never in production) |

> ⚠️ **Critical:** If `SECRET_KEY` changes, all existing sessions are invalidated. Every logged-in user will be forced to re-login.

---

## Maintenance & Known Issues

### Routine Maintenance

- **New team members:** Created via Team tab in dashboard. Default password is `test@123`. User must change on first login.
- **New flavours/SKUs:** Added via Flavours tab. Prices are set per region.
- **New city/region:** Requires adding a `user_role` enum value in DB, adding the role to `REGION_HEAD_ROLES` dict in `order_engine.py`, and mapping in `_PLACE_TO_CITY`, `_CITY_TO_REGION_ROLE`, `_REGION_ROLE_TO_ORDER_CODE`, `_ORDER_CODE_TO_CITY`.
- **Orphan auth users:** If a team member creation fails partway, a Supabase Auth user may exist without a matching `sales.users` row. Clean up via Supabase dashboard → Authentication → Users.

### Known Considerations

- **Cold starts:** Vercel serverless functions have cold start latency. Heavy imports (ReportLab, openpyxl) are deferred to avoid penalizing common routes.
- **SKU data fallback:** If Supabase is unreachable at import time, the app uses hardcoded `MOCK_SKUS`. This means any SKUs added after the last code deploy won't appear until the database reconnects.
- **IST timezone:** Server runs on UTC. All date logic uses `_today_ist()` to convert to IST. Be careful with date boundaries around midnight.
- **Session revalidation:** The 300-second cache means a deactivated user could still make requests for up to 5 minutes.
- **Google Form sync is fire-and-forget:** If the form submission fails, the order is already created. No retry mechanism.
- **Historical orders in old format:** ~1,117 Tally-imported orders retain old-format numbers (e.g. `MU1/26-27/123`) for accounting audit trail. The trigger only converts on new inserts.

### Adding a New Integration

1. For read-only: add an endpoint with `@tally_api_key_required` and a new API key env var
2. For Google Sheets: copy the pattern from `SheetSync.gs`, store service_role key in ScriptProperties
3. For new Google Form: add form URL in `google_form_sync.py`, map city to form

### Common Debugging

- **Order creation fails:** Check `create_order()` in order_engine.py. It has rollback logic — if line insertion fails, the order is deleted.
- **"GENERATED ALWAYS" errors:** Never include `id` in INSERT statements for orders or order_lines tables.
- **Price not found:** Check `sku_prices` table — ensure there's an active row (effective_to IS NULL or >= today) for the region.
- **Client not found in sync:** The sheet sync auto-creates clients. Check the fuzzy matching threshold in `lookupClientId_()`.

---

## Contacts & Access

### Access Credentials Required

- **GitHub repo:** `icestasy-projects/icestasy-order-desk` — need collaborator access
- **Vercel:** Project deployment dashboard — need team member access
- **Supabase:** Project `acngdpcpxburkzqxjpbf` — need organization member access
- **Google Apps Script:** Access to the Google Sheets containing sync_orders.gs and SheetSync.gs
- **Groq:** API key for LLM parsing (optional, system works without it)
- **Google Forms:** Access to the Mumbai and Pune order collection forms

### Key Files Quick Reference

| What | Where |
|------|-------|
| All routes + auth | `app.py` |
| Core business logic | `order_engine.py` |
| Order text AI parsing | `parser.py` |
| PDF invoices | `invoicing.py` |
| Excel exports | `reports.py` |
| SKU catalog + aliases | `sku_data.py` |
| Google Form push | `google_form_sync.py` |
| Tally sheet sync | `scripts/sync_orders.gs` |
| Main sheet sync | `scripts/google-sheets-sync/SheetSync.gs` |
| Dashboard UI | `templates/dashboard.html` |
| Order form UI | `templates/index.html` |

---

> ✅ **Handover complete.** This document covers the full system architecture, database, API surface, business logic, and operational knowledge needed to maintain the Icestasy Order Desk application. For sales/operations usage guide, see the companion Sales Handover document.
