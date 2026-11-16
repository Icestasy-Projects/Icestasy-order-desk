# Icestasy Order Desk: Operations Handover

## 1. What the App Does

The Icestasy Order Desk is the central system for managing B2B ice cream orders. It handles the full order-to-invoice workflow:

- Receive orders via WhatsApp text (AI-parsed) or manual entry
- Track order status from draft through approval, invoicing, dispatch, and delivery
- Generate GST-compliant PDF invoices with UPI QR codes
- Manage B2B clients (HoReCa and distributors) with regional pricing
- Track payments and outstanding dues
- Produce MIS reports (daily, weekly, monthly) and Excel exports
- Manage city-wise stock and factory requisitions

Production URL: **icestasyorders.vercel.app**

## 2. Accessing the App & User Roles

### First Login

1. Your admin creates your account and gives you an email and temporary password (`test@123`)
2. On first login, you are prompted to set a new password
3. You land on the Dashboard — what you see depends on your role

Your session stays active for 30 days. You only need to log in again if you clear browser data or your account is deactivated.

### Role Hierarchy

| Role | Scope | Key Abilities |
|------|-------|---------------|
| **Admin** | All cities, all actions | Approvals, team management, flavour editing, client admin, full MIS |
| **Regional Head** | Own region only | View region orders/team/stock, create salespeople, approve region orders |
| **Salesperson** | Own orders only | Create orders, register clients, view own orders |
| **Accounts / Production / Manager** | Limited | Login access, specific feature access |

### Permission Matrix

| Action | Salesperson | Regional Head | Admin |
|--------|------------|---------------|-------|
| Create orders | Yes | Yes | Yes |
| View all orders (region/all) | No | Own region | All cities |
| Approve / Reject orders | No | Own region | All |
| Download invoices | Own orders | Own region | All |
| Excel exports | Own orders | Own region | All |
| View MIS / Insights / Dues | No | Own region | All |
| Register clients | Yes | Yes | Yes |
| Edit / Delete clients | No | No | Yes |
| Add team members | No | Salespeople in own region | Any role |
| Reset passwords / Delete staff | No | No | Yes (admin only) |
| Manage flavours / prices | No | View only | Full edit |
| Stock requests | No | Create for own city | Approve / Reject |

## 3. Creating Orders

### WhatsApp Text Parsing (Primary Method)

The fastest way to enter orders. The system reads natural-language WhatsApp messages and converts them into structured order lines.

1. Click **New Order** from the dashboard
2. Paste the WhatsApp message into the text box and click **Parse**
3. The AI extracts flavour names, quantities, and pack formats
4. Review and adjust — edit quantities, remove items, or add more manually
5. Select the client and choose billing/shipping addresses
6. Review totals and submit

> **Parsing tips:** The parser understands Hindi and Marathi names (e.g. "hapoos" = Ratnagiri Hapoos Mango), common abbreviations ("choco" = Chocolate), and handles typos. Best format: "Belgian 5, Mango 3, Vanilla 2".

### Manual Order Entry

Skip parsing and build the order manually by selecting flavours and quantities from the picker interface.

### Sample Orders

Toggle to **Sample** mode to create sample/tasting orders. These go into a separate tracking system with outcome tracking: converted to commercial order, rejected, or no response.

### Order Number Format

```
{CITY}/{YY}/{MM}/{SEQ:04d}
Example: MUM/26/11/0296
```

| Code | Region |
|------|--------|
| MUM | Mumbai, Thane, Navi Mumbai, Vasai-Virar |
| PUN | Pune |
| BLR | Bangalore |
| HYD | Hyderabad |
| DEL | Delhi |
| ROI | Rest of India |

### Order Status Flow

```
Draft → Approved → Invoiced → In Production → Dispatched → Delivered
  │
  ├→ Hold (client has unpaid orders) → Released → Approved
  ├→ Rejected (by admin)
  └→ Cancelled (by creator)
```

| Status | Meaning |
|--------|---------|
| Draft | New order, awaiting admin review |
| Hold | Auto-applied when client has unpaid previous orders. Admin can manually hold/release. |
| Approved | Ready for production and invoicing |
| Invoiced | Invoice generated, ready for dispatch |
| Dispatched / Delivered | Fulfilment stages |
| Rejected / Cancelled | Terminal states |

> **Auto-Hold rule:** When a client has existing pending (unpaid) orders, new orders from them are automatically placed on hold. The admin must review and release.

## 4. Client Management

### Client Types

| Type | Description | Pricing |
|------|-------------|---------|
| **HoReCa** | Hotels, Restaurants, Cafes, Parlours | Standard regional pricing |
| **Distributor** | B2B distributors / dealers | May have special ROI pricing |

### Adding a New Client

1. From the **Clients** tab or during order creation, click **Add Client**
2. Fill in: Business name, type (HoReCa/Distributor), phone, city
3. Optional: GSTIN, FSSAI number, email, contact name
4. Add at least one billing address (with state, pincode, GSTIN)
5. Optionally add a shipping address if different from billing

> **Tax rule:** The state code on the shipping address determines whether the invoice shows CGST+SGST (intrastate, within Maharashtra) or IGST (interstate). Make sure the state is correct.

### Client Statuses

| Status | Effect |
|--------|--------|
| Active | Normal — can place orders |
| Inactive | Temporarily paused |
| Blacklisted | Blocked from placing orders |

Admin can edit client details, change cities, update addresses, and perform bulk-move or bulk-delete operations.

## 5. Payments & Dues

### Payment Modes

- **Advance:** Client pays before dispatch (default for most clients)
- **Invoice / Credit:** Client pays after receiving goods

### Recording Payments

On the Orders tab, click **Mark Paid** on any order:

| Payment Type | When Used |
|-------------|-----------|
| Full payment | Entire order amount at once |
| Advance payment | Partial amount before dispatch |
| Balance payment | Remaining amount after delivery |

### Dues Tracking

The **Dues** tab shows all clients with outstanding balances:

- Total due = Sum of (order total − payments received) for all non-cancelled orders
- Click any client for a per-order breakdown
- Useful for follow-up calls on outstanding payments

> **Impact on new orders:** Clients with unpaid orders will have their new orders automatically placed on hold until the admin reviews.

## 6. Invoices & Exports

### PDF Invoices

Click the invoice icon on any approved/invoiced order. The invoice includes:

| Field | Detail |
|-------|--------|
| Company | Icestasy Projects Pvt. Ltd. |
| GSTIN | 27AAECI1609N1ZE |
| Line items | HSN-coded with quantities and prices |
| Tax | CGST + SGST (within Maharashtra) or IGST (interstate) |
| Payment | UPI QR code (Icestasy@icici) |
| Balance | Running client balance / previous dues |
| Amount in words | Indian numbering (lakhs, crores) |

### Excel Exports

The **Export** button on the dashboard creates downloadable Excel workbooks:

| Export Type | Content | Best For |
|-------------|---------|----------|
| All Orders | Multi-sheet workbook, one sheet per month | Complete record keeping |
| By Month | Single month's orders | Monthly review / Tally entry |
| By City | Orders filtered by city | Regional head reporting |
| By Client | One client's full order history | Client meetings, credit review |
| By Salesperson | One salesperson's orders | Performance reviews |
| Flavour Report | Summary + detail by flavour/SKU | Product planning |
| Client List | All clients with contact info | CRM export |

> **Tally compatibility:** Exports include Voucher Type, HSN codes, and CGST/SGST/IGST columns that map directly to Tally's import format.

## 7. MIS Reports

The **MIS** tab provides three views of sales performance:

| View | Scope | Grouping |
|------|-------|----------|
| Daily | Today's sales | By city |
| Weekly | Current week (Mon–Sat) | One row per day, by city |
| Monthly | Current month | By week number, by city |

> **For Sales Heads:** Use the Monthly view at the start of each week to track against targets. The city breakdown shows which regions are performing and which need attention.

### Insights Tab

Separate from MIS, the **Insights** tab focuses on product performance:

- Which flavours are selling most (by quantity and value)
- Which pack formats are popular
- City-wise flavour preferences
- Regional heads see only their region; admin sees all

## 8. Stock Management

### Factory Stock (FG)

The Stock tab's first view shows factory finished goods inventory. This is read from the production system and is read-only from this app.

### City-Wise Stock

Each city maintains its own stock count:

| Metric | Calculation |
|--------|-------------|
| Dispatched | From approved stock requests |
| Used | Consumed by orders from that city |
| Available | Dispatched − Used |

### Stock Requests (Regional Heads)

1. Go to Stock tab → **Request Stock**
2. Select the SKUs and quantities needed
3. Submit the request
4. Admin reviews and approves (may adjust quantities) or rejects
5. Approved quantity adds to the city's stock

### Pre-Order Stock Check

When creating an order, the system checks city stock levels. If stock is low, a warning appears — but it is advisory, not blocking.

## 9. Flavours & Pricing

### SKU Structure

```
Belgian Chocolate (Flavour)
  ├── Belgian Chocolate - 4L Bulk    (SKU, ₹850)
  ├── Belgian Chocolate - 12 Square  (SKU, ₹480)
  └── Belgian Chocolate - 50ml       (SKU, free samples)
```

### Pack Formats

| Format | Default Price (INR) |
|--------|---------------------|
| 4L Bulk | 850 |
| 12 Square | 480 |
| 50ml Samples | 0 (free) |
| Extras | 50 |
| B2B Add-on | 300 |
| 500ml | 150 |

### Regional Pricing

Different cities can have different prices for the same SKU. Price lookup order:

1. Client's specific city region (e.g. "mumbai", "pune")
2. "default" region (base price)
3. "roi" region (Rest of India)
4. Hardcoded fallback (rarely used)

> **Date-effective pricing:** When a price changes, the old price is preserved with an end date. Historical orders always show the price they were placed at.

### Managing Flavours (Admin Only)

- **Add Flavour:** Create name, then add SKUs for each pack format
- **Set Price:** Per-SKU, per-region, date-effective
- **Discontinue:** Removed from order form; historical orders preserved

## 10. Team Management

### Adding Team Members

1. Go to the **Team** tab → **Add Member**
2. Fill in: Full name, email, phone, role, region
3. System creates a login account with default password `test@123`
4. Share the email and temporary password
5. They must change their password on first login

> **Regional heads** can only add salespeople in their own region. Only admins can create head or admin accounts.

### Managing Existing Members

| Action | Who Can Do It | Notes |
|--------|---------------|-------|
| Edit details | Admin, Heads (own region) | Name, email, phone, role, region |
| Deactivate | Admin only | Soft-delete — order history preserved |
| Reset Password | Admin only | Generates new temporary password |
| Permanent Delete | Admin only | Only if no linked orders or data |

## 11. Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| "I can't see any orders" | Salespeople only see their own orders | Create your first order, or check with admin |
| "My order is on Hold" | Client has unpaid previous orders | Ask admin to collect dues and mark paid, or release hold |
| "Parser didn't understand" | Message format too complex | Use clear format: "Belgian 5, Mango 3". Adjust manually after parsing. |
| "Can't find a client" | Search matches by business name | Type first few characters. Register new client if needed. |
| "Price seems wrong" | Regional pricing differs | Check with admin if pricing needs updating for your region |
| "Forgot my password" | N/A | Contact admin — they reset from Team tab |
| "Invoice shows IGST instead of CGST/SGST" | Shipping address state incorrect | Check client's shipping address state is correct |
| "Flavour not showing up" | May be discontinued or inactive | Contact admin to check Flavours tab |

### Getting Help

- **Technical issues** (system errors, page not loading, data discrepancies): Contact the tech manager
- **Operational questions** (pricing, client setup, approvals): Contact the admin or your regional head

> **Reference:** This guide covers day-to-day operations. For technical system details, deployment, and database documentation, see the companion Technical Handover document.
