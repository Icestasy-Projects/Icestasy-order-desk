/**
 * Icestasy Order Desk — Google Sheets → Supabase Sync
 *
 * SETUP:
 *   1. Open your Google Sheet (same format as Book2.xlsx)
 *   2. Extensions → Apps Script → paste this entire file
 *   3. Run onOpen() once to create the menu
 *   4. Click "Icestasy Sync → Setup API Key" and enter your
 *      Supabase service_role key (Dashboard → Settings → API → service_role)
 *   5. Make sure the "sales" schema is exposed:
 *      Dashboard → Settings → API → Exposed schemas → add "sales"
 *   6. Add column N header: "Sync Status"
 *
 * USAGE:
 *   Click "Icestasy Sync → Sync New Orders to DB"
 *   Only rows without "SYNCED" in column N will be processed.
 *
 * SHEET FORMAT (same as Book2.xlsx):
 *   A: B Type  |  B: Year  |  C: Date  |  D: Invoice  |  E: Billing
 *   F: Client  |  G: Flavour  |  H: Qty  |  I: Amt Pre  |  J: Amt Post
 *   K: Amt OS  |  L: Billed By  |  M: Product  |  N: Sync Status
 *
 *   Summary rows: have Invoice but NO Flavour → order totals
 *   Line item rows: have Invoice AND Flavour → individual SKU lines
 */

var SUPABASE_URL = 'https://acngdpcpxburkzqxjpbf.supabase.co';

// ── Column indices (0-based) ──
var COL_DATE     = 2;  // C
var COL_INVOICE  = 3;  // D
var COL_BILLING  = 4;  // E
var COL_CLIENT   = 5;  // F
var COL_FLAVOUR  = 6;  // G
var COL_QTY      = 7;  // H
var COL_AMT_PRE  = 8;  // I
var COL_AMT_POST = 9;  // J
var COL_SYNC     = 13; // N

// ── Flavour name mapping: Excel lowercase → DB flavour name ──
var FLAVOUR_MAP = {
  'dakkhan sitaphal':       'Dakkhan Sitaphal (Custard Apple)',
  'amrood':                 'Amrood (Guava/Peru)',
  'ratnagiri haapoos':      'Ratnagiri Hapoos (Mango)',
  'ratnagiri hapoos':       'Ratnagiri Hapoos (Mango)',
  'ukadiche modak':         'Ukadiche Modak',
  'gulqand':                'Gulqand',
  'chikkamagaluru kaaphi':  'Chikkamagaluru Kaaphi',
  'karikku':                'Karikku (Tender Coconut)',
  'vanilla vantage (fd)':   'Vanilla Vantage (FD)',
  'vanilla vantage':        'Vanilla Vantage (FD)',
  'cookie dusk':            'Cookie Dusk',
  'kesar thandai':          'Kesar Thandai',
  'belgian speculoos':      'Belgian Speculoos',
  'palaapazham':            'Palaapazham (Jackfruit)',
  'crumble & dough':        'Crumble and Dough',
  'crumble and dough':      'Crumble and Dough',
  'mysore paak':            'Mysore Paak',
  'salted caramel':         'Salted Caramel',
  'reshmi paan':            'Reshmi Paan',
  'dakshin laddoo':         'Dakshin Laddoo',
  'khajoor':                'Khajoor',
  'madagascar vanilla':     'Madagascar Vanilla',
  'kyoka kuro goma':        'Kyoka Kuro Goma',
  'kuro goma':              'Kyoka Kuro Goma',
  'aale paak':              'Aale Paak',
  'strawberry strength (fd)': 'Strawberry Strength (FD)',
  'french vanilla':         'French Vanilla',
  'gud & saunf':            'Gud & Sauf',
  'gud & sauf':             'Gud & Sauf',
  'kashmiri kesar':         'Kashmiri Kesar',
  'japanese matcha':        'Japanese Matcha',
  'gajar halwa':            'Gajar Halwa',
  'sunkissed twilight':     'Sunkissed Twilight',
  'apple pie':              'Apple Pie',
  'midnight mania':         'Midnight Mania (Ultra Dark Chocolate)',
  'vegan chocolate':        'Vegan Chocolate',
  'puranpoli':              'Puranpoli',
  'kaffir lime coconut':    'Kaffir Lime Coconut',
  'hara pista':             'Hara Pista',
  'ramphal':                'Ramphal',
  'yorkshire butterscotch': 'Yorkshire Butterscotch',
  'mango basil':            'Mango Basil',
  'mango mania (fd)':       'Mango Mania (FD)',
  'hass avocado':           'Hass Avocado',
  'strawberry cream':       'Strawberry Cream',
  'kaju katli':             'Kaju Katli',
  'shahi sevaiya':          'Shahi Sevaiya',
  'fd chocolate':           'FD Chocolate',
  'blueberry blush (fd)':   'Blueberry Blush (FD)',
  'banana caramel':         'Banana Caramel',
  'chikoo':                 'Chikoo',
  'cutting chai biskoot':   'Cutting Chai Biskoot',
  'hass avocado':           'Hass Avocado',
  'kashmiri kesar':         'Kashmiri Kesar',
  'miso caramel':           'Miso Caramel',
  'naarali bhaat':          'Naarali Bhaat',
  'off season sitaphal':    'Off Season Sitaphal',
  'qubaani':                'Qubaani (Apricots)',
  'signature strawberry':   'Signature Strawberry (Rosaea)',
  'signature strawberry (rosaea)': 'Signature Strawberry (Rosaea)',
  'strawberry cream':       'Strawberry Cream',
  'tilgul':                 'Tilgul',
  'vegan mango':            'Vegan Mango',
  'wasabi punch':           'Wasabi Punch'
};

// Discontinued — return null to skip
var DISCONTINUED = {
  'chocolate choice (fd)': true,
  'caramelized popcorn': true,
  'gulab jamun': true,
  'banarasi meetha paan': true,
  'jambhul': true,
  'sheer qhurma': true
};

// ── SKU ID lookup: DB flavour name → {format_id: sku_id} ──
// format_id: 1 = 4L Bulk, 2 = 12 Square, 3 = 50ml Samples
var DB_SKUS = {
  'Aale Paak':                              {1: 351},
  'Amrood (Guava/Peru)':                    {1: 269, 2: 289, 3: 309},
  'Apple Pie':                              {1: 352},
  'Banana Caramel':                         {1: 353},
  'Belgian Speculoos':                      {1: 270, 2: 290, 3: 310},
  'Blueberry Blush (FD)':                   {1: 383},
  'Chikkamagaluru Kaaphi':                  {1: 273, 2: 291, 3: 311},
  'Chikoo':                                 {1: 354},
  'Cookie Dusk':                            {1: 271, 2: 292, 3: 312},
  'Crumble and Dough':                      {1: 379},
  'Cutting Chai Biskoot':                   {1: 355},
  'Dakkhan Sitaphal (Custard Apple)':       {1: 272, 2: 293, 3: 313},
  'Dakshin Laddoo':                         {1: 356},
  'FD Chocolate':                           {1: 350},
  'French Vanilla':                         {1: 274, 2: 294, 3: 314},
  'Gajar Halwa':                            {1: 357},
  'Gud & Sauf':                             {1: 349},
  'Gulqand':                                {1: 275, 2: 295, 3: 315},
  'Hara Pista':                             {1: 358},
  'Hass Avocado':                           {1: 359},
  'Japanese Matcha':                        {1: 360},
  'Kaffir Lime Coconut':                    {1: 276, 2: 296, 3: 316},
  'Kaju Katli':                             {1: 277, 2: 297, 3: 317},
  'Karikku (Tender Coconut)':               {1: 278, 2: 298, 3: 318},
  'Kashmiri Kesar':                         {1: 361},
  'Kesar Thandai':                          {1: 279, 2: 299, 3: 319},
  'Khajoor':                                {1: 362},
  'Kyoka Kuro Goma':                        {1: 280, 2: 300, 3: 320},
  'Madagascar Vanilla':                     {1: 363},
  'Mango Basil':                            {1: 364},
  'Mango Mania (FD)':                       {1: 382},
  'Midnight Mania (Ultra Dark Chocolate)':  {1: 365},
  'Miso Caramel':                           {1: 366},
  'Mysore Paak':                            {1: 281, 2: 301, 3: 321},
  'Naarali Bhaat':                          {1: 367},
  'Off Season Sitaphal':                    {1: 380},
  'Palaapazham (Jackfruit)':                {1: 282, 2: 302, 3: 322},
  'Puranpoli':                              {1: 368},
  'Qubaani (Apricots)':                     {1: 369},
  'Ramphal':                                {1: 370},
  'Ratnagiri Hapoos (Mango)':               {1: 283, 2: 303, 3: 323},
  'Reshmi Paan':                            {1: 284, 2: 304, 3: 324},
  'Salted Caramel':                         {1: 285, 2: 305, 3: 325},
  'Shahi Sevaiya':                          {1: 371},
  'Signature Strawberry (Rosaea)':          {1: 378},
  'Strawberry Cream':                       {1: 372},
  'Strawberry Strength (FD)':               {1: 381},
  'Sunkissed Twilight':                     {1: 286, 2: 306, 3: 326},
  'Tilgul':                                 {1: 373},
  'Ukadiche Modak':                         {1: 287, 2: 307, 3: 327},
  'Vanilla Vantage (FD)':                   {1: 288, 2: 308, 3: 328},
  'Vegan Chocolate':                        {1: 374},
  'Vegan Mango':                            {1: 375},
  'Wasabi Punch':                           {1: 376},
  'Yorkshire Butterscotch':                 {1: 377}
};


// ═══════════════════════════════════════════════
//  MENU & SETUP
// ═══════════════════════════════════════════════

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Icestasy Sync')
    .addItem('Sync New Orders to DB', 'syncOrdersToDb')
    .addSeparator()
    .addItem('Setup API Key', 'setupApiKey')
    .addItem('Test Connection', 'testConnection')
    .addToUi();
}

function setupApiKey() {
  var ui = SpreadsheetApp.getUi();
  var result = ui.prompt(
    'Supabase Service Role Key',
    'Paste your service_role key from Supabase Dashboard → Settings → API.\n' +
    'This is stored securely in Script Properties (not visible in the sheet).',
    ui.ButtonSet.OK_CANCEL
  );
  if (result.getSelectedButton() === ui.Button.OK) {
    var key = result.getResponseText().trim();
    if (key.length < 20) {
      ui.alert('Key looks too short. Please check and try again.');
      return;
    }
    PropertiesService.getScriptProperties().setProperty('SUPABASE_KEY', key);
    ui.alert('API key saved successfully!');
  }
}

function getApiKey_() {
  var key = PropertiesService.getScriptProperties().getProperty('SUPABASE_KEY');
  if (!key) throw new Error('No API key set. Use Icestasy Sync → Setup API Key first.');
  return key;
}

function testConnection() {
  var ui = SpreadsheetApp.getUi();
  try {
    var key = getApiKey_();
    var clients = supabaseGet_('clients', 'select=id&limit=1');
    ui.alert('Connection successful! Found ' + clients.length + ' client(s).');
  } catch (e) {
    ui.alert('Connection failed: ' + e.message);
  }
}


// ═══════════════════════════════════════════════
//  SUPABASE REST API HELPERS
// ═══════════════════════════════════════════════

function supabaseGet_(table, queryParams) {
  var key = getApiKey_();
  var url = SUPABASE_URL + '/rest/v1/' + table + '?' + queryParams;
  var resp = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: {
      'apikey': key,
      'Authorization': 'Bearer ' + key,
      'Accept-Profile': 'sales',
      'Accept': 'application/json'
    },
    muteHttpExceptions: true
  });
  var code = resp.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error('GET ' + table + ' failed (' + code + '): ' + resp.getContentText());
  }
  return JSON.parse(resp.getContentText());
}

function supabaseInsert_(table, data) {
  var key = getApiKey_();
  var url = SUPABASE_URL + '/rest/v1/' + table;
  var resp = UrlFetchApp.fetch(url, {
    method: 'post',
    headers: {
      'apikey': key,
      'Authorization': 'Bearer ' + key,
      'Content-Profile': 'sales',
      'Content-Type': 'application/json',
      'Prefer': 'return=representation',
      'Accept': 'application/json'
    },
    payload: JSON.stringify(data),
    muteHttpExceptions: true
  });
  var code = resp.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error('INSERT ' + table + ' failed (' + code + '): ' + resp.getContentText());
  }
  return JSON.parse(resp.getContentText());
}


// ═══════════════════════════════════════════════
//  FLAVOUR / SKU PARSING
// ═══════════════════════════════════════════════

function detectFormatId_(formatStr) {
  if (!formatStr) return null;
  var lower = formatStr.toLowerCase();
  if (lower.indexOf('4 ltr') >= 0 || lower.indexOf('4l') >= 0)       return 1;
  if (lower.indexOf('12 square') >= 0)                                return 2;
  if (lower.indexOf('50 ml') >= 0 || lower.indexOf('sample') >= 0)   return 3;
  return null;
}

function parseFlavourToSku_(flavourStr) {
  if (!flavourStr || String(flavourStr).trim() === '') return null;

  var str = String(flavourStr).trim();
  var lastDash = str.lastIndexOf(' - ');
  if (lastDash < 0) return null;

  var rawName = str.substring(0, lastDash).trim().toLowerCase();
  var formatPart = str.substring(lastDash + 3).trim();

  if (DISCONTINUED[rawName]) return null;

  var dbName = FLAVOUR_MAP[rawName];
  if (!dbName) return null;

  var formatId = detectFormatId_(formatPart);
  if (!formatId) return null;

  var skuMap = DB_SKUS[dbName];
  if (!skuMap) return null;

  var skuId = skuMap[formatId] || skuMap[1];
  return skuId || null;
}


// ═══════════════════════════════════════════════
//  CLIENT CACHE
// ═══════════════════════════════════════════════

var clientCache_ = {};

function lookupClientId_(clientName) {
  if (!clientName) return null;
  var name = String(clientName).trim();
  if (clientCache_[name] !== undefined) return clientCache_[name];

  var encoded = encodeURIComponent(name);
  var results = supabaseGet_('clients', 'select=id&business_name=eq.' + encoded + '&limit=1');
  var id = (results.length > 0) ? results[0].id : null;
  clientCache_[name] = id;
  return id;
}


// ═══════════════════════════════════════════════
//  MAIN SYNC
// ═══════════════════════════════════════════════

function syncOrdersToDb() {
  var ui = SpreadsheetApp.getUi();
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = sheet.getDataRange().getValues();

  if (data.length < 2) {
    ui.alert('No data rows found.');
    return;
  }

  // Group rows by invoice number
  var orderMap = {};  // invoice → {summary, lines[], rowIndices[]}
  var skippedNoInvoice = 0;

  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    var invoice = row[COL_INVOICE];
    if (!invoice || String(invoice).trim() === '') {
      skippedNoInvoice++;
      continue;
    }

    invoice = String(invoice).trim();

    // Skip non-Pune invoices and credit notes
    if (invoice.indexOf('PU') !== 0 || invoice.indexOf('CN') === 0) continue;

    // Skip already synced
    var syncStatus = row[COL_SYNC] ? String(row[COL_SYNC]).trim() : '';
    if (syncStatus === 'SYNCED') continue;

    if (!orderMap[invoice]) {
      orderMap[invoice] = { summary: null, lines: [], rowIndices: [] };
    }

    var od = orderMap[invoice];
    od.rowIndices.push(i + 1); // 1-based row for sheet updates

    var flavour = row[COL_FLAVOUR];
    var hasFlavour = flavour && String(flavour).trim() !== '';

    if (!hasFlavour) {
      // Summary row
      od.summary = {
        date: row[COL_DATE],
        billing: row[COL_BILLING] ? String(row[COL_BILLING]).trim() : '',
        client: row[COL_CLIENT] ? String(row[COL_CLIENT]).trim() : '',
        subtotal: parseFloat(row[COL_AMT_PRE]) || 0,
        total: parseFloat(row[COL_AMT_POST]) || 0
      };
    } else {
      // Line item row
      var qty = parseFloat(row[COL_QTY]) || 0;
      var amtPre = parseFloat(row[COL_AMT_PRE]) || 0;
      var skuId = parseFlavourToSku_(flavour);

      if (skuId && qty > 0) {
        od.lines.push({
          sku_id: skuId,
          quantity: qty,
          unit_price: Math.round((amtPre / qty) * 100) / 100,
          line_total: Math.round(amtPre * 100) / 100
        });
      }
    }
  }

  var invoices = Object.keys(orderMap);
  if (invoices.length === 0) {
    ui.alert('No new orders to sync. All rows are either already synced or have no invoice.');
    return;
  }

  // Confirm
  var validCount = 0;
  var lineCount = 0;
  for (var k = 0; k < invoices.length; k++) {
    if (orderMap[invoices[k]].summary && orderMap[invoices[k]].lines.length > 0) {
      validCount++;
      lineCount += orderMap[invoices[k]].lines.length;
    }
  }

  var confirmResult = ui.alert(
    'Confirm Sync',
    'Found ' + validCount + ' orders with ' + lineCount + ' line items to sync.\n' +
    '(' + (invoices.length - validCount) + ' orders skipped: no summary or no lines)\n\n' +
    'Proceed?',
    ui.ButtonSet.YES_NO
  );
  if (confirmResult !== ui.Button.YES) return;

  // Process each order
  var synced = 0;
  var errors = [];
  var log = [];

  for (var j = 0; j < invoices.length; j++) {
    var inv = invoices[j];
    var od = orderMap[inv];

    if (!od.summary || od.lines.length === 0) {
      log.push(inv + ': SKIP (no summary or no lines)');
      continue;
    }

    try {
      var clientName = od.summary.client || od.summary.billing;
      if (!clientName) {
        errors.push(inv + ': No client name');
        continue;
      }

      // Look up client
      var clientId = lookupClientId_(clientName);
      if (!clientId) {
        // Try billing name as fallback
        clientId = lookupClientId_(od.summary.billing);
      }
      if (!clientId) {
        errors.push(inv + ': Client not found — "' + clientName + '"');
        continue;
      }

      // Format date
      var dateStr = null;
      if (od.summary.date) {
        var d = od.summary.date;
        if (d instanceof Date) {
          dateStr = d.toISOString();
        } else {
          dateStr = String(d);
        }
      }

      // Insert order
      var orderData = {
        order_no: inv,
        client_id: clientId,
        channel: 'whatsapp',
        order_type: 'commercial',
        payment_mode: 'invoice',
        status: 'delivered',
        source: 'sheet_sync',
        subtotal_amount: od.summary.subtotal,
        discount_amount: 0,
        tax_amount: 0,
        total_amount: od.summary.total,
        notes: '[Sheet sync] ' + clientName
      };
      if (dateStr) {
        orderData.created_at = dateStr;
      }

      var insertedOrders = supabaseInsert_('orders', orderData);
      if (!insertedOrders || insertedOrders.length === 0) {
        errors.push(inv + ': Order insert returned empty');
        continue;
      }
      var orderId = insertedOrders[0].id;

      // Insert order lines
      var lineData = [];
      for (var li = 0; li < od.lines.length; li++) {
        lineData.push({
          order_id: orderId,
          sku_id: od.lines[li].sku_id,
          quantity: od.lines[li].quantity,
          unit_price: od.lines[li].unit_price,
          line_discount_amount: 0,
          line_total: od.lines[li].line_total,
          status: 'delivered'
        });
      }
      supabaseInsert_('order_lines', lineData);

      // Mark rows as synced
      for (var ri = 0; ri < od.rowIndices.length; ri++) {
        sheet.getRange(od.rowIndices[ri], COL_SYNC + 1).setValue('SYNCED');
      }

      synced++;
      log.push(inv + ': OK (' + od.lines.length + ' lines)');

    } catch (e) {
      errors.push(inv + ': ' + e.message);
    }
  }

  // Report
  var msg = 'Sync complete!\n\n' +
    'Synced: ' + synced + ' orders\n' +
    'Errors: ' + errors.length + '\n';

  if (errors.length > 0) {
    msg += '\nErrors:\n' + errors.slice(0, 20).join('\n');
    if (errors.length > 20) msg += '\n... and ' + (errors.length - 20) + ' more';
  }

  Logger.log('=== SYNC LOG ===');
  Logger.log(log.join('\n'));
  Logger.log('=== ERRORS ===');
  Logger.log(errors.join('\n'));

  ui.alert('Sync Results', msg, ui.ButtonSet.OK);
}
