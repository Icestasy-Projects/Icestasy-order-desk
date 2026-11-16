# Icestasy Order Desk

## Sales & Operations Guide

**November 2026**

---

## Getting Started

### What is the Order Desk?

The Icestasy Order Desk is your central hub for managing B2B ice cream orders. It handles everything from receiving orders via WhatsApp to generating GST invoices, tracking payments, and producing sales reports. Think of it as a lightweight ERP tailored for Icestasy's order-to-invoice workflow.

### First Login

1. **Get your credentials**
   Your admin will create your account and give you an email and temporary password (`test@123` by default).

2. **Log in and change your password**
   On first login, you'll be asked to set a new password. Choose something strong — this is your permanent login.

3. **Explore the dashboard**
   You'll land on the Dashboard. What you see depends on your role — salespeople see their own orders; regional heads and admins see everything for their scope.

> 💡 **Tip:** Your session stays active for 30 days. You won't need to log in again unless you clear your browser data or your account is deactivated.

---

## The Dashboard

The dashboard is a single-page app with multiple tabs. Here's what each tab does:

### Orders Tab

Your primary workspace. Shows all orders with status, client name, amounts, and dates.

- **Search:** Filter by order number, client name, or salesperson
- **Status filters:** Draft, Approved, Invoiced, Dispatched, Delivered, Hold, Cancelled
- **Bulk actions:** Select multiple orders for bulk operations
- **Order details:** Click any order to expand and see line items

### Clients Tab

All registered B2B clients. Search, add new clients, edit details, manage addresses.

### Team Tab

Staff management (admin/heads only). Create accounts, assign roles and regions, reset passwords.

### Insights Tab

Flavour and SKU sales analysis. See what's selling, by which format, in which city.

### Dues Tab

Outstanding payment tracker. Shows each client's total due amount, broken down by order.

### Stock Tab

Two views: factory finished goods (FG) stock and city-wise stock (what's been dispatched to each city vs. what's been consumed).

### Flavours Tab

SKU and flavour administration. Add flavours, set pack formats, manage prices per region. Admin only for editing; all roles can view.

### MIS Tab

Management Information System reports — daily, weekly, and monthly sales summaries with city breakdowns.

---

## Creating Orders

### The Smart Way: WhatsApp Text Parsing

The system can read natural-language WhatsApp messages and convert them into structured orders. This is the fastest way to enter orders.

1. **Click "New Order"**
   From the dashboard, click the New Order button to open the order form.

2. **Paste the WhatsApp message**
   Copy the order message from WhatsApp and paste it into the text box. Click "Parse". The AI will extract flavour names, quantities, and pack formats.

3. **Review and adjust**
   Check the parsed items. You can adjust quantities, remove items, or add more manually. Prices are auto-filled based on the client's region.

4. **Select client and addresses**
   Search and pick the client. Choose billing and shipping addresses. Add a new client or address on the fly if needed.

5. **Submit**
   Review totals and submit. The order enters "Draft" status and appears on the dashboard.

> 💡 **Parsing tips:** The parser understands Hindi and Marathi names (e.g. "hapoos" = Ratnagiri Hapoos Mango), common abbreviations ("choco" = Chocolate), and handles typos. It works best with messages like "Belgian 5, Mango 3, Vanilla 2" or similar formats.

### Manual Order Entry

If you prefer, you can skip parsing and build the order manually by selecting flavours and quantities from the picker interface.

### Sample Orders

Toggle to "Sample" mode to create sample/tasting orders. These go into a separate tracking system with outcome tracking (converted to commercial order / rejected / no response).

### Order Number Format

Every order gets an automatic number:

**`MUM/26/11/0296`**

> City code / Year / Month / Sequence number

City codes: MUM (Mumbai region), PUN (Pune), BLR (Bangalore), HYD (Hyderabad), DEL (Delhi), ROI (Rest of India).

### Order Status Flow

```
Draft  →  Approved  →  Invoiced  →  Dispatched  →  Delivered
  │
  ├→  Hold (pending payment or review)  →  Released → Approved
  ├→  Rejected (by admin)
  └→  Cancelled (by creator)
```

- **Draft:** New order, waiting for admin review
- **Hold:** Auto-applied when the client has unpaid previous orders. Admin can manually hold/release.
- **Approved:** Ready for production and invoicing
- **Invoiced:** Invoice generated, ready for dispatch
- **Dispatched / Delivered:** Fulfilment stages
- **Rejected / Cancelled:** Terminal states

> ℹ️ **Auto-Hold:** When a client has existing pending (unpaid) orders, new orders from them are automatically placed on hold. The admin must review and release.

---

## Client Management

### Client Types

| Type | Description | Pricing Impact |
|------|-------------|----------------|
| **HoReCa** | Hotels, Restaurants, Cafes, Ice Cream Parlours | Standard regional pricing |
| **Distributor** | B2B distributors / dealers | May have special pricing; ROI dealers get ROI pricing |

### Adding a New Client

1. From the **Clients** tab or during order creation, click "Add Client"
2. Fill in: Business name, type (HoReCa/Distributor), phone number, city
3. Optional: GSTIN, FSSAI number, email, contact name
4. Add at least one billing address (with state, pincode, GSTIN)
5. Optionally add a shipping address if different from billing

> 💡 **Address GSTIN matters for tax:** The state code on the shipping address determines whether the invoice shows CGST+SGST (intrastate, within Maharashtra) or IGST (interstate, outside Maharashtra). Make sure the state is correct.

### Client Status

- **Active:** Normal — can place orders
- **Inactive:** Temporarily paused
- **Blacklisted:** Blocked from placing orders

### Editing Clients (Admin Only)

Admins can edit client details, change cities, update addresses, and bulk-move or bulk-delete clients via the admin panel on the Clients tab.

---

## Payments & Dues

### Payment Modes

- **Advance:** Client pays before dispatch. Default for most clients.
- **Invoice / Credit:** Client pays after receiving goods, within agreed credit terms.

### Recording Payments

On the Orders tab, click "Mark Paid" on any order. You can record:

- **Full payment** — entire order amount
- **Advance payment** — partial amount before dispatch
- **Balance payment** — remaining amount after delivery

### Dues Tracking

The **Dues** tab shows all clients with outstanding balances:

- Total due = Sum of (order total - payments received) for all non-cancelled orders
- Click any client to see the per-order breakdown
- Useful for follow-up calls on outstanding payments

> ⚠️ **Impact on new orders:** Clients with unpaid orders will have their new orders automatically placed on hold until the admin reviews.

---

## MIS Reports

The MIS tab gives you three views of sales performance:

### Daily View

Today's sales broken down by city. Shows total orders, total amount, and order count for each city active today.

### Weekly View

Current week (Monday–Sunday), one row per day, with sales by city. See the daily trend and which days are strongest.

### Monthly View

Current month, grouped by week number. Shows progressive totals and city-wise breakdowns for planning.

> 💡 **For Sales Heads:** Use the Monthly view at the start of each week to track against targets. The city breakdown shows which regions are performing and which need attention.

### Insights Tab

Separate from MIS, the **Insights** tab focuses on product performance:

- Which flavours are selling most (by quantity and value)
- Which pack formats are popular
- City-wise flavour preferences
- Regional heads see only their region's data; admin sees all

---

## Exports & Invoices

### PDF Invoices

Click the invoice icon on any approved/invoiced order to download a PDF invoice. The invoice includes:

- Company header: Icestasy Projects Pvt. Ltd.
- GSTIN: 27AAECI1609N1ZE
- Consignee and buyer details
- HSN-coded line items with quantities and prices
- Tax breakdown: CGST + SGST (within Maharashtra) or IGST (interstate)
- UPI QR code for easy payment (Icestasy@icici)
- Running client balance / previous dues
- Amount in words (Indian numbering: lakhs, crores)

### Excel Exports

The Export button on the dashboard creates downloadable Excel workbooks. Available export types:

| Export Type | What You Get | Best For |
|-------------|-------------|----------|
| All Orders | Multi-sheet workbook, one sheet per month | Complete record keeping |
| By Month | Single month's orders | Monthly review / Tally entry |
| By City | Orders filtered by city | Regional head reporting |
| By Client | One client's full history | Client meetings, credit review |
| By Salesperson | One salesperson's orders | Performance reviews |
| Flavour Report | Summary + detail by flavour/SKU | Product planning, production |
| Client List | All clients with contact info | CRM export |

> ℹ️ **Tally Integration:** The Excel exports are formatted to be compatible with Tally accounting software. They include Voucher Type, HSN codes, and CGST/SGST/IGST columns that map to Tally's import format.

---

## Stock Management

### Factory Stock (FG Stock)

The Stock tab's first view shows the factory's finished goods (FG) inventory — what's available at the Icestasy factory for dispatch. This is read from the production system and is read-only.

### City-Wise Stock

Each city maintains its own stock count:

- **Dispatched:** What's been sent to the city (from approved stock requests)
- **Used:** What's been consumed by orders from that city
- **Available = Dispatched - Used**

### Stock Requests (Regional Heads)

Regional heads can request stock from the factory:

1. Go to Stock tab → "Request Stock"
2. Select the SKUs and quantities needed
3. Submit the request
4. Admin reviews and approves (may adjust quantities) or rejects
5. Once approved, the dispatched quantity adds to the city's stock

### Pre-Order Stock Check

When creating an order, the system checks if the city has enough stock for the requested items. If stock is low, you'll see a warning — but you can still proceed with the order.

---

## Team Management

### Adding Team Members (Admin / Heads)

1. Go to the **Team** tab
2. Click "Add Member"
3. Fill in: Full name, email, phone, role, and region
4. The system creates a login account with default password `test@123`
5. Share the email and temporary password with the new team member
6. They must change their password on first login

> ℹ️ **Note:** Regional heads can only add salespeople in their own region. Only admins can create head or admin accounts.

### Managing Existing Members

- **Edit:** Update name, email, phone, role, region
- **Deactivate:** Soft-delete — they can't log in but their order history is preserved
- **Reset Password:** Generate a new temporary password (admin only)
- **Permanent Delete:** Only if they have no orders or other data linked (admin only)

---

## Flavours & Pricing

### Flavour Structure

Each ice cream flavour can have multiple pack formats (SKUs):

```
Belgian Chocolate (Flavour)
  ├── Belgian Chocolate - 4L Bulk    (SKU, INR 850)
  ├── Belgian Chocolate - 12 Square  (SKU, INR 480)
  └── Belgian Chocolate - 50ml       (SKU, free samples)
```

### Managing Flavours (Admin Only)

- **Add Flavour:** Create a new flavour name, then add SKUs for each pack format
- **Edit Flavour:** Rename or update status
- **Discontinue:** Mark as discontinued (won't appear in order form, but historical orders are preserved)
- **Add SKU:** Add a new pack format to an existing flavour
- **Set Price:** Prices are per-SKU, per-region, and date-effective

### Regional Pricing

Different cities/regions can have different prices for the same SKU. The system looks up prices in this order:

1. The client's specific city region (e.g. "mumbai", "pune")
2. "default" region (the base price)
3. "roi" region (Rest of India pricing)
4. Hardcoded fallback prices (rarely used, only if database is unavailable)

> 💡 **When you change a price:** The old price is preserved with an end date (yesterday). A new price row starts today. This means historical orders always show the price they were placed at, even after a price change.

---

## Roles & Permissions

### Who Can Do What

**Admin**
Full access. All cities. All actions including team management, approvals, flavour editing, client admin.

**Regional Head**
Mumbai, Pune, Bangalore, Hyderabad, Delhi, or ROI Head. Sees their region's orders, team, and stock. Can create salespeople in their region.

**Salesperson**
Creates orders, registers clients, views their own orders. Cannot see other salespeople's orders or access admin features.

### Permission Matrix

| Action | Salesperson | Regional Head | Admin |
|--------|------------|---------------|-------|
| Create orders | Yes | Yes | Yes |
| View own orders | Yes | Yes | Yes |
| View all orders (region/all) | No | Own region | All cities |
| Approve / Reject orders | No | Own region | All |
| Download invoices | Own orders | Own region | All |
| Excel exports | Own orders | Own region | All |
| View MIS reports | No | Own region | All |
| View Insights | No | Own region | All |
| View Dues | No | Own region | All |
| Register clients | Yes | Yes | Yes |
| Edit / Delete clients | No | No | Yes |
| Add team members | No | Salespeople in own region | Any role |
| Reset passwords | No | No | Yes (admin only) |
| Delete team members | No | No | Yes (admin only) |
| Manage flavours / prices | No | View only | Full edit |
| Stock requests | No | Create for own city | Approve / Reject |
| View factory stock | No | Yes | Yes |

---

## Troubleshooting

### Common Issues

**"I can't see any orders"**
Salespeople only see their own orders. If you're a new salesperson with no orders yet, the dashboard will be empty. Create your first order to see it appear.

**"My order is on Hold"**
Orders are auto-held when the client has unpaid previous orders. Ask the admin to either collect the dues and mark paid, or manually release the hold if appropriate.

**"The parser didn't understand my WhatsApp message"**
Try reformatting: use clear flavour names and quantities. "Belgian 5, Mango 3" works better than "pls send 5 belgian choco and three mangoes asap thx". You can always adjust items manually after parsing, or skip parsing entirely.

**"I can't find a client"**
The search matches by business name. Try typing the first few characters. If the client doesn't exist yet, click "Register New Client" in the order form to add them.

**"The price seems wrong"**
Prices depend on the client's city/region. A Mumbai client and a Pune client may see different prices for the same SKU. Check with the admin if pricing needs to be updated for your region.

**"I forgot my password"**
Contact your admin. They can reset your password from the Team tab (this generates a new temporary password). You'll need to change it on your next login.

**"My invoice shows IGST instead of CGST/SGST (or vice versa)"**
This depends on the shipping address state. If the state is Maharashtra, the invoice shows CGST + SGST. Any other state shows IGST. Check that the client's shipping address has the correct state.

**"Some flavour I want isn't showing up"**
It may be discontinued or not yet added. Contact the admin to check the Flavours tab. Flavours can be active, inactive, or discontinued. Only active flavours with active SKUs appear in the order form.

### Getting Help

For technical issues (system errors, page not loading, data discrepancies), contact the tech manager. For operational questions (pricing, client setup, approvals), contact the admin or your regional head.

> ✅ **Quick Reference:** This guide covers the day-to-day operations of the Order Desk. For technical system details, deployment, and database documentation, see the companion Technical Handover document.
