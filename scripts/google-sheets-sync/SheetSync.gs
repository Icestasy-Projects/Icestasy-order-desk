/**
 * Icestasy Order Desk — Google Sheets → Supabase Sync
 *
 * SETUP:
 *   1. Open your Google Sheet (Sales Paste 2026 or similar)
 *   2. Extensions → Apps Script → paste this entire file
 *   3. Run onOpen() once to create the menu
 *   4. Click "Icestasy Sync → Setup API Key" and enter your
 *      Supabase service_role key (Dashboard → Settings → API →
 *      Legacy anon, service_role tab → copy service_role)
 *   5. Make sure the "sales" schema is exposed:
 *      Integrations → Data API → Settings → Exposed schemas → add "sales"
 *
 * USAGE:
 *   Click "Icestasy Sync → Sync New Orders to DB"
 *   Only rows without "SYNCED" in the Sync Status column will be processed.
 *   If it hits the 6-minute limit, it auto-continues via a time trigger.
 *   Use "Stop Auto-Sync" to cancel any pending auto-continuation.
 *
 * SHEET FORMAT (Sales Paste 2026):
 *   A: (unused) | B: B-Type  |  C: Date  |  D: Invoice  |  E: Billing
 *   F: Client   | G: Flavour |  H: Qty   |  I: Amt Pre  |  J: Amt Post
 *
 *   Summary rows: Flavour is empty OR "Null Flavour" → order totals
 *   Line item rows: Flavour has actual name (e.g. "Amrood - 4 Ltrs") → SKU lines
 */

var SUPABASE_URL = 'https://acngdpcpxburkzqxjpbf.supabase.co';

// Stop processing 60s before the 6-minute Apps Script limit
var MAX_RUNTIME_MS = 300000;

// ── Column indices (0-based) ──
var COL_BTYPE    = 1;  // B
var COL_DATE     = 2;  // C
var COL_INVOICE  = 3;  // D
var COL_BILLING  = 4;  // E
var COL_CLIENT   = 5;  // F
var COL_FLAVOUR  = 6;  // G
var COL_QTY      = 7;  // H
var COL_AMT_PRE  = 8;  // I
var COL_AMT_POST = 9;  // J

// Sync Status goes in the first empty column after your data.
// Adjust this if your sheet has more columns after J.
var COL_SYNC     = 13; // N

// ── Flavour name mapping: Excel lowercase → DB flavour name ──
var FLAVOUR_MAP = {
  'aale paak':              'Aale Paak',
  'amrood':                 'Amrood (Guava/Peru)',
  'apple pie':              'Apple Pie',
  'banana caramel':         'Banana Caramel',
  'belgian speculoos':      'Belgian Speculoos',
  'blueberry blush (fd)':   'Blueberry Blush (FD)',
  'blueberry blush':        'Blueberry Blush (FD)',
  'chikkamagaluru kaaphi':  'Chikkamagaluru Kaaphi',
  'chikoo':                 'Chikoo',
  'cookie dusk':            'Cookie Dusk',
  'crumble & dough':        'Crumble and Dough',
  'crumble and dough':      'Crumble and Dough',
  'cutting chai biskoot':   'Cutting Chai Biskoot',
  'dakkhan sitaphal':       'Dakkhan Sitaphal (Custard Apple)',
  'dakshin laddoo':         'Dakshin Laddoo',
  'fd chocolate':           'FD Chocolate',
  'french vanilla':         'French Vanilla',
  'gajar halwa':            'Gajar Halwa',
  'gud & saunf':            'Gud & Sauf',
  'gud & sauf':             'Gud & Sauf',
  'gulqand':                'Gulqand',
  'hara pista':             'Hara Pista',
  'hass avocado':           'Hass Avocado',
  'japanese matcha':        'Japanese Matcha',
  'kaffir lime coconut':    'Kaffir Lime Coconut',
  'kaju katli':             'Kaju Katli',
  'karikku':                'Karikku (Tender Coconut)',
  'kashmiri kesar':         'Kashmiri Kesar',
  'kesar thandai':          'Kesar Thandai',
  'khajoor':                'Khajoor',
  'kuro goma':              'Kyoka Kuro Goma',
  'kyoka kuro goma':        'Kyoka Kuro Goma',
  'madagascar vanilla':     'Madagascar Vanilla',
  'mango basil':            'Mango Basil',
  'mango mania (fd)':       'Mango Mania (FD)',
  'mango mania':            'Mango Mania (FD)',
  'midnight mania':         'Midnight Mania (Ultra Dark Chocolate)',
  'miso caramel':           'Miso Caramel',
  'mysore paak':            'Mysore Paak',
  'naarali bhaat':          'Naarali Bhaat',
  'off season sitaphal':    'Off Season Sitaphal',
  'palaapazham':            'Palaapazham (Jackfruit)',
  'puranpoli':              'Puranpoli',
  'qubaani':                'Qubaani (Apricots)',
  'ramphal':                'Ramphal',
  'ratnagiri haapoos':      'Ratnagiri Hapoos (Mango)',
  'ratnagiri hapoos':       'Ratnagiri Hapoos (Mango)',
  'reshmi paan':            'Reshmi Paan',
  'salted caramel':         'Salted Caramel',
  'shahi sevaiya':          'Shahi Sevaiya',
  'signature strawberry (rosaea)': 'Signature Strawberry (Rosaea)',
  'signature strawberry':   'Signature Strawberry (Rosaea)',
  'strawberry cream':       'Strawberry Cream',
  'strawberry strength (fd)': 'Strawberry Strength (FD)',
  'strawberry strength':    'Strawberry Strength (FD)',
  'sunkissed twilight':     'Sunkissed Twilight',
  'tilgul':                 'Tilgul',
  'ukadiche modak':         'Ukadiche Modak',
  'vanilla vantage (fd)':   'Vanilla Vantage (FD)',
  'vanilla vantage':        'Vanilla Vantage (FD)',
  'vegan chocolate':        'Vegan Chocolate',
  'vegan mango':            'Vegan Mango',
  'wasabi punch':           'Wasabi Punch',
  'yorkshire butterscotch': 'Yorkshire Butterscotch'
};

// Flavours without SKUs in DB — skip silently
var NO_SKU = {
  'null flavour': true,
  'after hours': true,
  'banarasi meetha paan': true,
  'boondi': true,
  'caramelized popcorn': true,
  'cheese melt': true,
  'chocolate choice (fd)': true,
  'chocolate choice': true,
  'dates and almonds': true,
  'gulab jamun': true,
  'jambhul': true,
  'legal overdose': true,
  'mishti doi': true,
  'new york style cheesecake': true,
  'nutty naughty': true,
  'pandan purple yam': true,
  'pinni': true,
  'sheer qhurma': true,
  'signature chocolate (cacaoir)': true,
  'signature mango (aurum)': true,
  'tamrind & curry leaf': true,
  'tamarind & curry leaf': true,
  'turkish hazelnut': true,
  'vegan strawberry': true,
  'white knight': true
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
    .addItem('Stop Auto-Sync', 'stopAutoSync')
    .addSeparator()
    .addItem('Setup API Key', 'setupApiKey')
    .addItem('Test Connection', 'testConnection')
    .addToUi();
}

function setupApiKey() {
  var ui = SpreadsheetApp.getUi();
  var result = ui.prompt(
    'Supabase Service Role Key',
    'Paste your service_role key from Supabase Dashboard.\n' +
    'Settings → API Keys → Legacy tab → service_role.\n' +
    'Stored securely in Script Properties (not visible in the sheet).',
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

function stopAutoSync() {
  clearAutoTrigger_();
  PropertiesService.getScriptProperties().deleteProperty('SYNC_AUTO_CONTINUE');
  SpreadsheetApp.getActiveSpreadsheet().toast('Auto-sync stopped. No pending continuation.', 'Icestasy Sync', 5);
}


// ═══════════════════════════════════════════════
//  AUTO-TRIGGER MANAGEMENT
// ═══════════════════════════════════════════════

function clearAutoTrigger_() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'syncOrdersToDb') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
}

function scheduleAutoContinue_() {
  clearAutoTrigger_();
  PropertiesService.getScriptProperties().setProperty('SYNC_AUTO_CONTINUE', 'true');
  ScriptApp.newTrigger('syncOrdersToDb')
    .timeBased()
    .after(60 * 1000)
    .create();
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

function isSummaryFlavour_(flavourStr) {
  if (!flavourStr) return true;
  var str = String(flavourStr).trim();
  if (str === '') return true;
  if (str.toLowerCase().indexOf('null flavour') >= 0) return true;
  return false;
}

function parseFlavourToSku_(flavourStr) {
  if (!flavourStr || String(flavourStr).trim() === '') return null;

  var str = String(flavourStr).trim();
  var lastDash = str.lastIndexOf(' - ');
  if (lastDash < 0) return null;

  var rawName = str.substring(0, lastDash).trim().toLowerCase();
  var formatPart = str.substring(lastDash + 3).trim();

  if (NO_SKU[rawName]) return null;

  var dbName = FLAVOUR_MAP[rawName];
  if (!dbName) return { error: rawName };

  var formatId = detectFormatId_(formatPart);
  if (!formatId) return null;

  var skuMap = DB_SKUS[dbName];
  if (!skuMap) return null;

  var skuId = skuMap[formatId] || skuMap[1];
  return skuId ? { sku_id: skuId } : null;
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
//  MAIN SYNC (resumable, time-aware)
// ═══════════════════════════════════════════════

function syncOrdersToDb() {
  var startTime = new Date().getTime();
  var props = PropertiesService.getScriptProperties();
  var isAutoResume = props.getProperty('SYNC_AUTO_CONTINUE') === 'true';

  // Clear auto-continue flag — we're running now
  props.deleteProperty('SYNC_AUTO_CONTINUE');
  clearAutoTrigger_();

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getActiveSheet();
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();

  ss.toast('Finding header and date range...', 'Icestasy Sync', -1);

  // Find header row (look for "Invoice" in first 5 rows)
  var headerData = sheet.getRange(1, 1, Math.min(5, lastRow), lastCol).getValues();
  var headerRow = -1;
  for (var h = 0; h < headerData.length; h++) {
    for (var c = 0; c < headerData[h].length; c++) {
      if (String(headerData[h][c]).trim().toLowerCase() === 'invoice') {
        headerRow = h;
        break;
      }
    }
    if (headerRow >= 0) break;
  }
  if (headerRow < 0) {
    ss.toast('Could not find header row with "Invoice" column.', 'Icestasy Sync', 10);
    return;
  }

  var dataStartRow = headerRow + 2; // 1-indexed sheet row where data begins
  var totalDataRows = lastRow - dataStartRow + 1;
  if (totalDataRows <= 0) {
    ss.toast('No data rows found below the header.', 'Icestasy Sync', 10);
    return;
  }

  // Only sync June–September 2026
  var SYNC_FROM  = new Date(2026, 5, 1);  // June 1, 2026
  var SYNC_UNTIL = new Date(2026, 9, 1);  // October 1, 2026 (exclusive)
  var dates = sheet.getRange(dataStartRow, COL_DATE + 1, totalDataRows, 1).getValues();

  // Find first row in range
  var yearStartIdx = -1;
  for (var d = 0; d < dates.length; d++) {
    var dt = dates[d][0];
    if (dt instanceof Date && dt >= SYNC_FROM && dt < SYNC_UNTIL) {
      yearStartIdx = d;
      break;
    }
  }

  if (yearStartIdx < 0) {
    ss.toast('No rows found for Jun–Sep 2026.', 'Icestasy Sync', 10);
    return;
  }

  // Find last row in range
  var yearEndIdx = yearStartIdx;
  for (var d2 = dates.length - 1; d2 >= yearStartIdx; d2--) {
    var dt2 = dates[d2][0];
    if (dt2 instanceof Date && dt2 >= SYNC_FROM && dt2 < SYNC_UNTIL) {
      yearEndIdx = d2;
      break;
    }
  }

  var syncStartRow = dataStartRow + yearStartIdx; // 1-indexed
  var syncRowCount = yearEndIdx - yearStartIdx + 1;

  ss.toast('Loading ' + syncRowCount + ' rows (Jun–Sep 2026)...', 'Icestasy Sync', -1);

  var data = sheet.getRange(syncStartRow, 1, syncRowCount, lastCol).getValues();

  // Group rows by invoice number, skipping already synced rows
  var orderMap = {};
  var skippedNoInvoice = 0;
  var skippedSynced = 0;
  var unknownFlavours = {};

  for (var i = 0; i < data.length; i++) {
    var row = data[i];

    var rowDate = row[COL_DATE];
    if (rowDate instanceof Date && (rowDate < SYNC_FROM || rowDate >= SYNC_UNTIL)) continue;

    var invoice = row[COL_INVOICE];
    if (!invoice || String(invoice).trim() === '') {
      skippedNoInvoice++;
      continue;
    }

    invoice = String(invoice).trim();

    // Skip already synced
    if (row.length > COL_SYNC) {
      var syncStatus = row[COL_SYNC] ? String(row[COL_SYNC]).trim() : '';
      if (syncStatus === 'SYNCED') {
        skippedSynced++;
        continue;
      }
    }

    if (!orderMap[invoice]) {
      orderMap[invoice] = { summary: null, lines: [], rowIndices: [], btype: '' };
    }

    var od = orderMap[invoice];
    od.rowIndices.push(syncStartRow + i);

    var btype = row[COL_BTYPE] ? String(row[COL_BTYPE]).trim() : '';
    if (btype) od.btype = btype;

    var flavour = row[COL_FLAVOUR];

    if (isSummaryFlavour_(flavour)) {
      od.summary = {
        date: row[COL_DATE],
        billing: row[COL_BILLING] ? String(row[COL_BILLING]).trim() : '',
        client: row[COL_CLIENT] ? String(row[COL_CLIENT]).trim() : '',
        subtotal: parseFloat(row[COL_AMT_PRE]) || 0,
        total: parseFloat(row[COL_AMT_POST]) || 0
      };
    } else {
      var qty = parseFloat(row[COL_QTY]) || 0;
      var amtPre = parseFloat(row[COL_AMT_PRE]) || 0;
      var parsed = parseFlavourToSku_(flavour);

      if (parsed && parsed.error) {
        unknownFlavours[parsed.error] = (unknownFlavours[parsed.error] || 0) + 1;
        continue;
      }

      if (parsed && parsed.sku_id && qty > 0) {
        od.lines.push({
          sku_id: parsed.sku_id,
          quantity: qty,
          unit_price: Math.round((amtPre / qty) * 100) / 100,
          line_total: Math.round(amtPre * 100) / 100
        });
      }
    }
  }

  var invoices = Object.keys(orderMap);

  // Count valid orders
  var validCount = 0;
  var lineCount = 0;
  for (var k = 0; k < invoices.length; k++) {
    if (orderMap[invoices[k]].summary && orderMap[invoices[k]].lines.length > 0) {
      validCount++;
      lineCount += orderMap[invoices[k]].lines.length;
    }
  }

  if (validCount === 0) {
    ss.toast(
      'No rows to process.' +
      (skippedSynced > 0 ? ' (' + skippedSynced + ' rows already marked SYNCED)' : ''),
      'Icestasy Sync', 10
    );
    return;
  }

  // Pre-fetch existing order_nos from Supabase to avoid duplicates
  ss.toast('Checking for existing orders in DB...', 'Icestasy Sync', -1);
  var existingOrders = {};
  var validInvoices = [];
  for (var vi = 0; vi < invoices.length; vi++) {
    if (orderMap[invoices[vi]].summary && orderMap[invoices[vi]].lines.length > 0) {
      validInvoices.push(invoices[vi]);
    }
  }
  // Check in batches of 50 (PostgREST URL length limit)
  for (var bi = 0; bi < validInvoices.length; bi += 50) {
    var batch = validInvoices.slice(bi, bi + 50);
    var inList = batch.map(function(inv) { return '"' + inv.replace(/"/g, '\\"') + '"'; }).join(',');
    var existing = supabaseGet_('orders', 'select=order_no&order_no=in.(' + encodeURIComponent(inList) + ')&limit=1000');
    for (var ei = 0; ei < existing.length; ei++) {
      existingOrders[existing[ei].order_no] = true;
    }
  }

  // Mark already-existing orders' rows as SYNCED and remove from processing
  var alreadyInDb = 0;
  for (var ai = 0; ai < invoices.length; ai++) {
    if (existingOrders[invoices[ai]]) {
      var od2 = orderMap[invoices[ai]];
      for (var ri2 = 0; ri2 < od2.rowIndices.length; ri2++) {
        sheet.getRange(od2.rowIndices[ri2], COL_SYNC + 1).setValue('SYNCED');
      }
      alreadyInDb++;
      delete orderMap[invoices[ai]];
    }
  }

  // Rebuild invoice list after removing duplicates
  invoices = Object.keys(orderMap);
  validCount = 0;
  lineCount = 0;
  for (var k2 = 0; k2 < invoices.length; k2++) {
    if (orderMap[invoices[k2]].summary && orderMap[invoices[k2]].lines.length > 0) {
      validCount++;
      lineCount += orderMap[invoices[k2]].lines.length;
    }
  }

  if (validCount === 0) {
    ss.toast(
      'No new orders to sync.' +
      (alreadyInDb > 0 ? ' (' + alreadyInDb + ' already in DB, marked SYNCED)' : '') +
      (skippedSynced > 0 ? ' (' + skippedSynced + ' rows already marked SYNCED)' : ''),
      'Icestasy Sync', 10
    );
    return;
  }

  // On manual run (not auto-resume), show confirmation
  if (!isAutoResume) {
    var ui = SpreadsheetApp.getUi();
    var confirmMsg = validCount + ' NEW orders with ' + lineCount + ' line items to sync.\n' +
      (alreadyInDb > 0 ? alreadyInDb + ' orders already in DB (skipped, marked SYNCED).\n' : '') +
      (skippedSynced > 0 ? skippedSynced + ' rows already marked SYNCED (skipped).\n' : '') +
      '(' + (invoices.length - validCount) + ' orders skipped: no summary or no mapped lines)\n';

    var unknownKeys = Object.keys(unknownFlavours);
    if (unknownKeys.length > 0) {
      confirmMsg += '\nUnmapped flavours (lines skipped):\n';
      for (var uk = 0; uk < Math.min(10, unknownKeys.length); uk++) {
        confirmMsg += '  - ' + unknownKeys[uk] + ' (' + unknownFlavours[unknownKeys[uk]] + ' lines)\n';
      }
      if (unknownKeys.length > 10) confirmMsg += '  ... and ' + (unknownKeys.length - 10) + ' more\n';
    }

    confirmMsg += '\nScript will auto-continue if it hits the time limit.\nProceed?';

    var confirmResult = ui.alert('Confirm Sync', confirmMsg, ui.ButtonSet.YES_NO);
    if (confirmResult !== ui.Button.YES) return;
  } else {
    ss.toast(
      'Auto-continuing sync: ' + validCount + ' new orders remaining' +
      (alreadyInDb > 0 ? ' (' + alreadyInDb + ' duplicates skipped)' : '') + '...',
      'Icestasy Sync', 5
    );
  }

  // Process each order with time check
  var synced = 0;
  var errors = [];
  var log = [];
  var timedOut = false;

  for (var j = 0; j < invoices.length; j++) {
    // Time check — stop before the limit
    var elapsed = new Date().getTime() - startTime;
    if (elapsed >= MAX_RUNTIME_MS) {
      timedOut = true;
      break;
    }

    var inv = invoices[j];
    var od = orderMap[inv];

    if (!od.summary || od.lines.length === 0) {
      continue;
    }

    try {
      var clientName = od.summary.client || od.summary.billing;
      if (!clientName) {
        errors.push(inv + ': No client name');
        continue;
      }

      var clientId = lookupClientId_(clientName);
      if (!clientId && od.summary.billing && od.summary.billing !== clientName) {
        clientId = lookupClientId_(od.summary.billing);
      }
      if (!clientId) {
        errors.push(inv + ': Client not found — "' + clientName + '"');
        continue;
      }

      // Format date
      var dateStr = null;
      if (od.summary.date) {
        var dd = od.summary.date;
        if (dd instanceof Date) {
          dateStr = dd.toISOString();
        } else if (String(dd).trim() !== '') {
          dateStr = String(dd);
        }
      }

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

      // Insert order lines (batch)
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

      // Progress toast every 50 orders
      if (synced % 50 === 0) {
        ss.toast('Synced ' + synced + ' orders so far...', 'Icestasy Sync', 3);
      }

    } catch (e) {
      errors.push(inv + ': ' + e.message);
    }
  }

  // Log results
  Logger.log('=== SYNC BATCH ===');
  Logger.log('Synced: ' + synced + ', Errors: ' + errors.length + ', Timed out: ' + timedOut);
  if (errors.length > 0) {
    Logger.log('=== ERRORS ===');
    Logger.log(errors.join('\n'));
  }

  if (timedOut) {
    // Schedule auto-continuation
    scheduleAutoContinue_();
    ss.toast(
      'Synced ' + synced + ' orders this run (' + errors.length + ' errors).\n' +
      'Time limit reached — auto-continuing in ~1 minute.\n' +
      'Use "Stop Auto-Sync" to cancel.',
      'Icestasy Sync', 15
    );
  } else {
    // All done
    var msg = 'Sync complete!\n' +
      'Synced: ' + synced + ' orders\n' +
      'Errors: ' + errors.length;

    if (errors.length > 0) {
      msg += '\n\nErrors:\n' + errors.slice(0, 20).join('\n');
      if (errors.length > 20) msg += '\n... and ' + (errors.length - 20) + ' more';
    }

    SpreadsheetApp.getUi().alert('Sync Results', msg, SpreadsheetApp.getUi().ButtonSet.OK);
  }
}
