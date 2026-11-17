# Icestasy Order Desk: Technical Handover

## 1. Tech Stack

### Frontend

- **Python / Flask 3.1.1** — single `app.py` entry point, server-rendered Jinja2 templates
- Vanilla HTML/CSS/JS (no build step, no frontend framework)
- Searchable dropdowns via `searchable-select.js`
- All pages are server-rendered templates; the dashboard is a single-page app with JS-driven tabs

### Backend / Data

- **Supabase**: Postgres DB + Auth + PostgREST API
- Project ID: `acngdpcpxburkzqxjpbf`
- Two DB schemas: `sales` (all order desk tables) and `production` (factory stock views, managed separately)
- Python SDK: `supabase-py` with service role key for all data operations

### Hosting

- Vercel, auto-deploys on push to `main`
- Production URL: icestasyorders.vercel.app
- Preview deploys on PRs

### Key Libraries

| Library | Purpose |
|---------|---------|
| `flask` 3.1.1 | Web framework, routes, session management |
| `supabase` (supabase-py) | Supabase client SDK for Postgres + Auth |
| `reportlab` 4.2.5 | PDF invoice generation (deferred import) |
| `openpyxl` 3.1.5 | Excel workbook generation (deferred import) |
| `qrcode[pil]` 8.0 | UPI payment QR codes on invoices |
| `groq` | LLM API for WhatsApp order text parsing (optional) |

> **Important:** Heavy imports (ReportLab, Pillow, openpyxl) are deferred to local imports inside the routes that use them, not at module level. This dramatically reduces cold-start time for all other routes on Vercel's serverless platform.

## 2. Repository & Deployment

### GitHub

- Repo: https://github.com/Icestasy-Projects/Icestasy-order-desk (private)
- Main branch: `main`, auto-deploys to production on Vercel
- Feature work is done on `claude/...` branches and merged via PR
- No CI pipeline beyond Vercel's own build check

### Vercel Deployment

- Every push to `main` triggers a production deployment
- Every PR gets a Preview deployment
- Build command: Vercel runs `@vercel/python` builder on `app.py`
- All requests routed via `vercel.json`:

```json
{
  "builds": [{ "src": "app.py", "use": "@vercel/python" }],
  "routes": [{ "src": "/(.*)", "dest": "app.py" }]
}
```

> **Important:** The `main` branch is the production branch. Never force-push to `main`. Always use pull requests for changes.

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

## 3. Environment Variables

| Variable | Where Set | Purpose |
|----------|-----------|---------|
| `SECRET_KEY` | Vercel → Production + Preview | Flask session secret (MUST be persistent across deploys) |
| `SUPABASE_URL` | Vercel → Production + Preview | Supabase project URL |
| `SUPABASE_ANON_KEY` | Vercel → Production + Preview | Supabase anon/public key (used for auth login) |
| `SUPABASE_SERVICE_KEY` | Vercel → Production + Preview (server only) | Service role key for all data operations. Never expose client-side. |
| `TALLY_API_KEY` | Vercel → Production + Preview | API key for `/api/tally/sales` M2M endpoint |
| `GROQ_API_KEY` | Vercel → Production (optional) | Groq API key for LLM-based order parsing. Falls back to keyword parser if missing. |

> **Security rule:** `SUPABASE_SERVICE_KEY` must only appear in server-side code. It is used in `order_engine.py` to create the Supabase admin client. It must never be hardcoded or exposed to the browser.

> **Critical:** If `SECRET_KEY` changes, all existing sessions are invalidated. Every logged-in user will be forced to re-login.

## 4. Database Architecture

All tables live in the `sales` schema (not the default `public` schema). There is also a `production` schema for factory stock views. Supabase PostgREST requires the schema prefix when calling from the client:

```python
sb.schema('sales').table('orders').select('*').execute()
```

### Core Tables (sales schema)

| Table | Purpose |
|-------|---------|
| `users` | Staff accounts. Linked to Supabase Auth via `auth_user_id`. Role: salesperson, admin, mumbai_head, etc. |
| `clients` | B2B customers (HoReCa or distributor). Business name, city, GSTIN, status. |
| `orders` | Commercial orders. `id` is `GENERATED ALWAYS` — never include in INSERTs. Order number format: `MUM/26/11/0296`. |
| `order_lines` | Line items per order. Also `GENERATED ALWAYS` identity. Links order → SKU with quantity and price. |
| `addresses` | Billing/shipping addresses per client, with GSTIN, state code, consignee name. |
| `flavours` | Flavour master list (name, status: active/inactive/discontinued). |
| `pack_formats` | Pack sizes: 4L Bulk, 12 Square, 50ml Samples, Extras, B2B Add-on, 500ml. |
| `skus` | SKU = flavour + pack_format. Has sku_code, HSN code, GST rate (default 5%). |
| `sku_prices` | Date-effective pricing per SKU per region (default, mumbai, pune, roi, etc.). |
| `payments` | Payment records: advance / balance / full, linked to order. |
| `sample_orders` | Sample/tasting orders (separate table, mirrors orders structure). |
| `sample_order_lines` | Sample order line items. |
| `sample_outcomes` | Track sample conversion: pending / converted / rejected / no_response. |
| `order_sequences` | Atomic order number counter per city_code + fiscal year. |
| `order_status_history` | Audit trail of order status changes. |
| `order_collateral` | Extra items (dry ice, spoons, etc.) attached to orders. |
| `discount_rules` | Configurable discount rules (advance payment, ROI dealer, volume). |
| `applied_discounts` | Which rules were applied to which orders. |
| `stock_requests` | City-wise stock requisitions from regional heads. |
| `stock_request_lines` | Line items per stock request (requested_qty / approved_qty). |

### Key Stored Functions

| Function | Purpose |
|----------|---------|
| `sales.next_order_seq(p_city_code, p_fy)` | Atomic sequence for order numbers. Uses INSERT...ON CONFLICT DO UPDATE to prevent race conditions. |
| `sales.next_sample_order_seq()` | Same pattern for sample orders. |
| `sales.get_dashboard_orders()` | Aggregated order data with client/salesperson joins for dashboard. |
| `sales.get_sample_orders()` | Sample orders for dashboard. |
| `sales.normalize_order_no()` | BEFORE INSERT trigger — auto-converts old-format order numbers to new format. |
| `sales.bulk_insert_orders_with_lines()` | Batch order import function. |
| `sales.get_fg_weekly_req()` | Factory finished goods weekly requirement. |

### Trigger

`trg_normalize_order_no` — BEFORE INSERT on `sales.orders`. Detects old-format order numbers (e.g. `PU11/26-27/60`) and auto-converts them to the new uniform format (`PUN/26/11/0060`) by mapping 2-letter to 3-letter city codes and calling `next_order_seq`.

### Enum Types

| Type | Values |
|------|--------|
| `user_role` | salesperson, accounts, production, manager, admin, onboarding, mumbai_head, pune_head, bangalore_head, hyderabad_head, delhi_head, roi_head |
| `order_status` | draft, hold, pending_approval, approved, rejected, cancelled, invoiced, in_production, dispatched, delivered |
| `client_type` | horeca, distributor |
| `client_status` | active, inactive, blacklisted |
| `payment_mode` | advance, invoice |
| `payment_type` | advance, balance, full |
| `payment_method` | upi, bank_transfer, cheque, cash |
| `sku_status` | active, inactive, discontinued |
| `sample_outcome` | pending, converted, rejected, no_response |
| `address_type` | billing, shipping |

### Production Schema Views

The `production` schema is managed separately (not in this codebase) and exposes views read by the app:

- `v_fg_stock` — Finished goods stock at factory
- `v_rm_stock` — Raw material stock
- `v_prep_stock` — Prep stock
- `v_stock_targets_fg`, `v_stock_targets_rm`, `v_stock_targets_prep` — Stock targets
- `v_stock_alerts_fg`, `v_stock_alerts_rm`, `v_stock_alerts_prep` — Stock alerts

## 5. Row-Level Security & Grants

RLS is enabled on all tables in the `sales` schema. Most tables use `service_role_all` policies (the app backend uses the service role key to bypass RLS).

Some catalog tables also allow `authenticated read` or `anon_select` for the Google Apps Scripts that use the anon key:

| Table | Extra Policy | Why |
|-------|-------------|-----|
| `clients` | `anon_select` | Google Apps Script client lookup |
| `flavours` | `anon_select` | Script needs flavour names |
| `pack_formats` | `anon_select` | Script needs format mapping |
| `skus` | `anon_select` | Script needs SKU resolution |
| `sku_prices` | `anon_select` | Script needs pricing |
| `discount_rules` | `authenticated read` | Script discount calculation |
| `sample_outcomes` | `authenticated read` | Dashboard reads |

### How to Diagnose RLS Issues

```sql
-- Check policies on a table
SELECT policyname, cmd, roles, qual
FROM pg_policies
WHERE schemaname = 'sales' AND tablename = 'your_table';

-- Check grants on a function
SELECT routine_name, grantee, privilege_type
FROM information_schema.role_routine_grants
WHERE routine_schema = 'sales' AND grantee = 'authenticated';
```

## 6. Authentication

Supabase Auth (email + password). No SSO/OAuth configured.

### Login Flow

1. User submits email + password to `POST /login`
2. App calls `sb.auth.sign_in_with_password()` against Supabase Auth
3. On success, looks up `sales.users` by email, checks `is_active`
4. Stores user_id, role, region, full_name in Flask server-side session
5. Session cookie: 30-day permanent, Secure, HttpOnly, SameSite=Lax
6. Session revalidated every 300 seconds (re-reads `sales.users` row)

`must_change_password` flag in `sales.users`: when true, the app redirects to `/change-password` immediately after login.

### Three Authorization Decorators

| Decorator | Who Gets Access | Used For |
|-----------|----------------|----------|
| `@admin_required` | admin + all regional heads (`BROAD_VIEW_ROLES`) | Most admin/dashboard endpoints |
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

## 7. API Routes

All API routes live in `app.py` and use the Supabase service role key (admin client) to bypass RLS.

### Pages (GET, return HTML)

| Route | Auth | Purpose |
|-------|------|---------|
| `/login` | Public | Login page (GET) and auth (POST) |
| `/logout` | Any | Clear session, redirect to login |
| `/change-password` | Any | Password change form |
| `/` | Any logged in | Dashboard (SPA) |
| `/new-order` | Any logged in | Order creation form |

### Order APIs

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/parse` | POST | Parse WhatsApp text → structured items |
| `/api/parse/flavour-options` | GET | All active SKUs with prices |
| `/api/reprice` | POST | Recalculate prices for changed items |
| `/api/orders` | POST | Create commercial order |
| `/api/sample-orders` | POST | Create sample order |
| `/api/orders/stock-check` | POST | Pre-order stock availability check |
| `/api/orders/<id>/cancel` | POST | Cancel order |
| `/api/orders/<id>/put-on-hold` | POST | Put order on hold (admin) |
| `/api/orders/<id>/release-hold` | POST | Release hold (admin) |

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
| `/api/dashboard/mis` | GET | MIS data (daily/weekly/monthly mode) |
| `/api/dashboard/flavour-sales` | GET | Flavour/SKU sales insights |

### Client APIs

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/clients/search` | GET | Search by name (typeahead) |
| `/api/clients` | GET/POST | Paginated list / register new client |
| `/api/clients/all-lite` | GET | Lightweight list for dropdowns |
| `/api/clients/export` | GET | Clients Excel |
| `/api/clients/dues` | GET | Client dues summary |
| `/api/clients/<id>/due-detail` | GET | Single client due breakdown |
| `/api/clients/<id>/addresses` | GET/POST | List / create addresses |
| `/api/admin/clients/<id>` | PATCH/DELETE | Update / delete client (admin) |
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
| `/api/admin/skus/<id>/status` | POST | Toggle SKU active/inactive |

### External / M2M APIs

| Route | Method | Auth | Purpose |
|-------|--------|------|---------|
| `/api/tally/sales` | GET | API Key | Tally-formatted sales data with HSN, GST split |

## 8. Order System

### Order Creation Flow

1. User pastes WhatsApp order text
2. **Parsing:** Two-tier system — Groq LLM primary (`llama-3.3-70b-versatile`), keyword/fuzzy fallback if LLM fails
3. **Resolution:** Parsed items matched to SKUs via fuzzy matching (`difflib.get_close_matches` at 0.8 cutoff)
4. **Pricing:** Prices loaded from `sku_prices` with region fallback chain: specific region → "default" → "roi" → MOCK_PRICES
5. User confirms/edits items, selects client and addresses
6. **Submission:** `create_order()` — atomic creation with rollback on failure
7. **Post-creation:** Order pushed to Google Form via `google_form_sync`

### Order Number Format

```
{3-letter CITY}/{YY}/{MM}/{SEQ:04d}
Examples: MUM/26/11/0296, PUN/26/11/0030, ROI/26/11/0001
```

City codes: MUM (Mumbai, Thane, Navi Mumbai, Vasai-Virar), PUN (Pune), BLR (Bangalore), HYD (Hyderabad), DEL (Delhi), ROI (rest of India).

Sequence generation is atomic via the `next_order_seq(p_city_code, p_fy)` RPC, which uses INSERT...ON CONFLICT DO UPDATE to prevent race conditions.

> A BEFORE INSERT trigger (`trg_normalize_order_no`) auto-converts old-format numbers (e.g. `PU11/26-27/60`) to the new format. Historical Tally imports retain their original format for audit trail preservation.

### Order Statuses

```
draft → hold (optional) → approved → invoiced → in_production → dispatched → delivered
  └→ rejected
  └→ cancelled
```

### Auto-Hold Logic

Orders from clients with existing pending (unpaid) orders are automatically put on hold. The `should_auto_hold()` function checks for pending orders from the same client.

### Pack Format Constraint

> **Business rule:** 500ml and 150ml pack formats are skipped when creating order lines. The `create_order()` function filters these out.

### Order Text Parser (parser.py)

- **Primary:** Groq LLM (`llama-3.3-70b-versatile`) extracts structured items from natural language
- **Fallback:** Keyword extraction with `_segment_line_items()` handles "Name qty" and "qty Name" patterns
- **Fuzzy matching:** `difflib.get_close_matches` at 0.8 cutoff for typo tolerance
- **Alias mapping:** Extensive alias dictionary in `sku_data.py` — Hindi/Marathi names, common misspellings
- **Ambiguous flavours:** Some names map to multiple SKUs (e.g. "Belgian" → Speculoos + Chocolate)
- **LLM output sanitization:** `_sanitize_extracted()` validates LLM output as untrusted data

### Discount System

Header-level percentage discount spread across order lines via `order_discount_factor()`. Each line gets: `line_discount = unit_price × qty × (1 - factor)` where factor = `(subtotal - discount) / subtotal`.

## 9. Pricing & SKUs

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

The system looks up prices in this order:

1. Client's specific city region (e.g. "mumbai", "pune")
2. "default" region (the base price)
3. "roi" region (Rest of India pricing)
4. Hardcoded `MOCK_PRICES` fallback (rarely used, only if database is unavailable)

### Date-Effective Pricing

When a new price is set via `set_sku_price()`, the previous price row's `effective_to` is set to yesterday, and a new row is created with `effective_from` = today. This preserves price history for reporting.

### SKU Data Loading

`sku_data.py` tries to load live SKU data from Supabase at import time. If Supabase is unavailable, it falls back to hardcoded `MOCK_SKUS` (~80 SKUs). This ensures the app can start even if the database is temporarily down.

## 10. Integrations

### Google Forms (Outbound)

File: `google_form_sync.py`

After every order is created in the web app, each order line is pushed as a separate Google Form response:

- **Mumbai form:** For orders in Mumbai, Vasai-Virar, Thane, Navi Mumbai
- **Pune form:** For all other cities

This mirrors the data into the master Google Sheets that the operations team uses for production planning.

### Google Forms (Inbound — gform_import)

External Google Forms/Apps Script (NOT in this repo) creates orders directly in Supabase. These show `source = 'gform_import'`. The Pune form historically used old-format order numbers, now auto-converted by the trigger.

### Tally Sync (sync_orders.gs)

File: `scripts/sync_orders.gs`

Google Apps Script that:

- Reads from the "Combined" sheet in the master Google Sheet
- Groups line items by Invoice number
- Upserts to Supabase via REST API (anon key)
- Filters: Mumbai/Pune only, existing clients only, rows after Sep 1, 2026
- Daily trigger at 10 PM IST
- Source: `gsheet_sync`

### Sheet Sync (SheetSync.gs)

File: `scripts/google-sheets-sync/SheetSync.gs`

More sophisticated sync with:

- Fuzzy client matching (3-tier: exact → normalised core + location scoring → auto-create)
- Extensive `FLAVOUR_MAP` mapping Excel names to DB names
- `NO_SKU` set for discontinued/unmapped flavours (skipped silently)
- Resumable sync (stops 60s before GAS 6-min limit, auto-continues via trigger)
- Marks synced rows in column N of the sheet
- Uses service_role key (stored in ScriptProperties, not hardcoded)
- Source: `sheet_sync`

### Tally API

`GET /api/tally/sales` — authenticated with `X-API-Key` header. Returns Tally-formatted sales data with:

- Voucher types: "Icecream Sale- Mumbai" / "Icecream Sale - Pune"
- HSN codes, GST rates
- CGST/SGST (intrastate) or IGST (interstate) split
- Used by Tally accounting software for automatic voucher creation

> **Interstate vs Intrastate:** Tax splitting uses `is_interstate_supply()` from order_engine.py. Intrastate (within Maharashtra) = CGST + SGST. Interstate = IGST. Based on shipping address state code.

## 11. Stock Management

### Factory FG Stock (Central)

Read from `production.v_fg_stock` view (managed by separate production system). Shown on the dashboard Stock tab. Read-only from this app.

### City-Wise Stock (Requisition/Dispatch)

Regional heads create `stock_requests` for their city. Admin approves (sets `approved_qty`) or rejects. City stock = total dispatched − total used (from order lines), excluding `historical_import` orders.

Cities with stock tracking: all cities from `REGION_HEAD_ROLES.values()`.

### Pre-Order Stock Check

`check_stock_for_order()` is called before order creation to warn if city stock is insufficient. It is advisory, not blocking.

## 12. Invoicing & Reports

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
- `mis_weekly_sales()` — Current week (Mon–Sat), grouped by date
- `mis_monthly_sales()` — Current month, grouped by week

## 13. Known Issues & Quirks

### Cold Starts

Vercel serverless functions have cold start latency. Heavy imports (ReportLab, openpyxl) are deferred to avoid penalizing common routes.

### SKU Data Fallback

If Supabase is unreachable at import time, the app uses hardcoded `MOCK_SKUS`. This means any SKUs added after the last code deploy won't appear until the database reconnects.

### IST Timezone

Server runs on UTC. All date logic uses `_today_ist()` to convert to IST. Be careful with date boundaries around midnight.

### Session Revalidation

The 300-second cache means a deactivated user could still make requests for up to 5 minutes.

### Google Form Sync

Fire-and-forget. If the form submission fails, the order is already created. No retry mechanism.

### Historical Orders in Old Format

~1,117 Tally-imported orders retain old-format numbers (e.g. `MU1/26-27/123`) for accounting audit trail. The trigger only converts on new inserts.

### TypeScript / Map Iteration

Not applicable to this codebase (Python/Flask), but the Google Apps Scripts that interact with this database are JavaScript and may hit GAS execution limits (6-minute max).

## 14. Key Contacts / Access

| System | Where to Find Credentials |
|--------|--------------------------|
| GitHub (`Icestasy-Projects` org) | Organisation owner can add collaborators |
| Vercel project | Vercel account settings. Request team access or transfer the project. |
| Supabase project `acngdpcpxburkzqxjpbf` | Supabase dashboard. Add a team member under Project Settings → Team. |
| Supabase service role key | Supabase dashboard → Project Settings → API → service_role (keep secret) |
| Google Apps Script (Tally sync) | Access to the Google Sheets containing sync_orders.gs and SheetSync.gs |
| Google Forms (Mumbai + Pune) | Access to the order collection forms |
| Groq API | groq.com — API key for LLM parsing (optional, system works without it) |

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
