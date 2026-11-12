/*
 * Icestasy Order Sync — Google Apps Script (v2)
 *
 * Reads from "Combined" sheet, groups line items by Invoice,
 * and upserts to Supabase sales.orders.
 *
 * FILTERS:
 *   - Only Mumbai / Pune orders (by B-Type column)
 *   - Only clients already registered in Supabase
 *   - Skips rows before START_DATE
 *
 * SETUP: Open Google Sheet → Extensions → Apps Script → Paste → Save → Run syncOrders()
 */

// ─── CONFIG ───
var SUPABASE_URL = 'https://acngdpcpxburkzqxjpbf.supabase.co';
var ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFjbmdkcGNweGJ1cmt6cXhqcGJmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE3OTg4MjcsImV4cCI6MjA5NzM3NDgyN30.t2XuMvFL5iyGeWkERJrTFPmJdNMb48gCUcn8Z0j5bsM';
var SHEET_NAME = 'Combined';
var HEADER_ROW = 2;
var BATCH_SIZE = 200;
var START_DATE = new Date(2026, 8, 1);  // Sep 1, 2026 (month is 0-indexed)

// Column positions (0-indexed)
var COL = {
  BTYPE: 1,      // B: B-Type (e.g. "Mumbai - B2B")
  DATE: 2,       // C: Date
  INVOICE: 3,    // D: Invoice
  BILLING: 4,    // E: Billing
  CLIENT: 5,     // F: Client
  FLAVOUR: 6,    // G: Flavour
  QTY: 7,        // H: Qty
  AMT_PRE: 8,    // I: Amt (Pre-gst)
  AMT_POST: 9,   // J: Amt (Post-gst)
  AMT_OS: 10,    // K: Amt (O/s)
  BILLED_BY: 11, // L: Billed By
  PRODUCT: 12    // M: Product
};

// Only sync these cities
var ALLOWED_CITIES = ['mumbai', 'pune'];

// ─── HELPERS ───

// Normalize a name for matching: lowercase, collapse whitespace, normalize dashes
function normalizeName_(name) {
  return String(name || '')
    .toLowerCase()
    .replace(/\s*[-–—]\s*/g, ' - ')   // normalize all dash variants with spaces
    .replace(/\s+/g, ' ')              // collapse whitespace
    .trim();
}

// Extract city from B-Type column (e.g. "Mumbai - B2B" → "mumbai")
function parseCity_(btype) {
  if (!btype) return '';
  return String(btype).split(/[-–—]/)[0].trim().toLowerCase();
}

// Check if city is Mumbai or Pune
function isMumbaiPune_(btype) {
  var city = parseCity_(btype);
  return ALLOWED_CITIES.indexOf(city) !== -1;
}

// Fetch all clients from Supabase and build a lookup map
function fetchClientMap_() {
  var clients = {};
  var offset = 0;
  var pageSize = 1000;

  while (true) {
    var resp = UrlFetchApp.fetch(
      SUPABASE_URL + '/rest/v1/clients?select=id,business_name&order=id&offset=' + offset + '&limit=' + pageSize,
      {
        method: 'get',
        headers: {
          'apikey': ANON_KEY,
          'Authorization': 'Bearer ' + ANON_KEY,
          'Accept-Profile': 'sales'
        },
        muteHttpExceptions: true
      }
    );

    if (resp.getResponseCode() !== 200) {
      Logger.log('Failed to fetch clients: ' + resp.getResponseCode() + ' ' + resp.getContentText().substring(0, 200));
      break;
    }

    var batch = JSON.parse(resp.getContentText());
    if (batch.length === 0) break;

    for (var i = 0; i < batch.length; i++) {
      var key = normalizeName_(batch[i].business_name);
      clients[key] = { id: batch[i].id, name: batch[i].business_name };
    }

    offset += batch.length;
    if (batch.length < pageSize) break;
  }

  Logger.log('Loaded ' + Object.keys(clients).length + ' clients from Supabase');
  return clients;
}

// ─── MAIN SYNC ───
function syncOrders() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAME);
  if (!sheet) { Logger.log('Sheet "' + SHEET_NAME + '" not found'); return; }

  // Load existing clients first
  var clientMap = fetchClientMap_();

  var props = PropertiesService.getScriptProperties();
  var lastRow = parseInt(props.getProperty('sync_last_row') || '0', 10);
  var startFrom = Math.max(lastRow, HEADER_ROW);

  var data = sheet.getDataRange().getValues();
  var totalRows = data.length;
  Logger.log('Sheet has ' + totalRows + ' rows. Starting from row ' + (startFrom + 1));

  // Group line items by Invoice
  var orders = {};
  var orderList = [];
  var skippedCity = 0;
  var skippedClient = 0;
  var unmatchedClients = {};

  for (var i = startFrom; i < totalRows; i++) {
    var r = data[i];
    var invoice = String(r[COL.INVOICE] || '').trim();
    if (!invoice) continue;

    var dt = r[COL.DATE];
    if (!(dt instanceof Date)) continue;
    if (dt < START_DATE) continue;

    var btype = String(r[COL.BTYPE] || '').trim();

    // ── Filter: Mumbai / Pune only ──
    if (!isMumbaiPune_(btype)) {
      skippedCity++;
      continue;
    }

    var client = String(r[COL.CLIENT] || '').trim();
    var billing = String(r[COL.BILLING] || '').trim();
    var flavour = String(r[COL.FLAVOUR] || '').trim();
    var qty = parseFloat(r[COL.QTY]) || 0;
    var preTax = parseFloat(r[COL.AMT_PRE]) || 0;
    var postTax = parseFloat(r[COL.AMT_POST]) || 0;

    // ── Filter: existing clients only ──
    var clientKey = normalizeName_(client);
    var matchedClient = clientMap[clientKey];
    if (!matchedClient) {
      skippedClient++;
      unmatchedClients[client] = (unmatchedClients[client] || 0) + 1;
      continue;
    }

    if (!orders[invoice]) {
      orders[invoice] = {
        order_no: invoice,
        created_at: Utilities.formatDate(dt, 'Asia/Kolkata', "yyyy-MM-dd'T'HH:mm:ss'+05:30'"),
        client_id: matchedClient.id,
        consignee_name: client,
        billing: billing,
        btype: btype,
        subtotal_amount: 0,
        total_amount: 0,
        items: []
      };
      orderList.push(invoice);
    }

    var o = orders[invoice];
    o.subtotal_amount += preTax;
    o.total_amount += postTax;
    o.items.push(flavour + (qty ? ' x' + qty : ''));
  }

  Logger.log('Skipped ' + skippedCity + ' rows (non Mumbai/Pune)');
  Logger.log('Skipped ' + skippedClient + ' rows (client not in Supabase)');

  // Log unmatched clients so user knows what to register
  var unmatchedList = Object.keys(unmatchedClients);
  if (unmatchedList.length > 0) {
    Logger.log('=== UNMATCHED CLIENTS (' + unmatchedList.length + ') ===');
    unmatchedList.sort();
    for (var u = 0; u < unmatchedList.length; u++) {
      Logger.log('  ' + unmatchedClients[unmatchedList[u]] + 'x  ' + unmatchedList[u]);
    }
  }

  // Build order records
  var records = [];
  for (var j = 0; j < orderList.length; j++) {
    var o = orders[orderList[j]];
    var tax = Math.round((o.total_amount - o.subtotal_amount) * 100) / 100;
    records.push({
      order_no: o.order_no,
      created_at: o.created_at,
      client_id: o.client_id,
      consignee_name: o.consignee_name,
      channel: o.btype,
      order_type: 'commercial',
      payment_mode: 'invoice',
      status: 'delivered',
      source: 'gsheet_sync',
      subtotal_amount: Math.round(o.subtotal_amount * 100) / 100,
      discount_amount: 0,
      tax_amount: tax > 0 ? tax : 0,
      total_amount: Math.round(o.total_amount * 100) / 100,
      notes: 'Billing: ' + o.billing + ' | Items: ' + o.items.join(', ')
    });
  }

  Logger.log('Orders to sync: ' + records.length);
  if (records.length === 0) { Logger.log('Nothing new to sync.'); return; }

  // Send in batches
  var sent = 0, errs = 0;
  for (var b = 0; b < records.length; b += BATCH_SIZE) {
    var batch = records.slice(b, b + BATCH_SIZE);
    var bn = Math.floor(b / BATCH_SIZE) + 1;
    var tb = Math.ceil(records.length / BATCH_SIZE);

    try {
      var resp = UrlFetchApp.fetch(SUPABASE_URL + '/rest/v1/orders', {
        method: 'post',
        contentType: 'application/json',
        headers: {
          'apikey': ANON_KEY,
          'Authorization': 'Bearer ' + ANON_KEY,
          'Content-Profile': 'sales',
          'Prefer': 'resolution=ignore-duplicates,return=minimal'
        },
        payload: JSON.stringify(batch),
        muteHttpExceptions: true
      });
      var code = resp.getResponseCode();
      if (code >= 200 && code < 300) {
        sent += batch.length;
        Logger.log('Batch ' + bn + '/' + tb + ': OK (' + batch.length + ' orders)');
      } else {
        errs += batch.length;
        Logger.log('Batch ' + bn + '/' + tb + ': ERROR ' + code + ' ' + resp.getContentText().substring(0, 300));
      }
    } catch (e) {
      errs += batch.length;
      Logger.log('Batch ' + bn + '/' + tb + ': EXCEPTION ' + e.message);
    }
  }

  // Save progress
  props.setProperty('sync_last_row', String(totalRows));

  Logger.log('=== DONE ===');
  Logger.log('Sent: ' + sent + ' | Errors: ' + errs);
  Logger.log('Next run starts from row ' + totalRows);
}

// Reset to re-sync everything from START_DATE
function resetSync() {
  PropertiesService.getScriptProperties().deleteProperty('sync_last_row');
  Logger.log('Reset done. Next syncOrders() processes all rows from START_DATE.');
}

// Auto-sync daily at 10 PM IST
function setupDailySync() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === 'syncOrders') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('syncOrders').timeBased().everyDays(1).atHour(22).create();
  Logger.log('Daily trigger set for 10 PM.');
}
