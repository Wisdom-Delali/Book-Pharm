// Book Pharm POS — renderer logic. No Node/Electron APIs here except the
// `window.deviceConfig` and `window.localDb` bridges exposed by preload.js;
// everything else (fetch, crypto.randomUUID, window.print) is standard web
// platform. Offline sync design follows CLAUDE.md §7: every sale is written
// to the local outbox before anything else, online or offline alike, and
// the outbox is drained by a retrying background worker.

let apiBaseUrl = null;
let apiToken = null;
let cart = []; // [{ book_id, title, author, unit_price, qty, cover_image, stock_qty }]
let loyaltyBalance = null; // null = no customer looked up yet (or offline/not found)
let loyaltyPointValueGhs = 0;

const $ = (id) => document.getElementById(id);

function money(n) {
  return `GHS ${Number(n).toFixed(2)}`;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

function showView(name) {
  $('view-settings').classList.toggle('hidden', name !== 'settings');
  $('view-app').classList.toggle('hidden', name !== 'app');
  if (name === 'app') {
    $('view-register').classList.remove('hidden');
    $('view-receipt').classList.add('hidden');
  }
}

function showReceiptView() {
  $('view-register').classList.add('hidden');
  $('view-receipt').classList.remove('hidden');
}

async function apiFetch(path, options = {}) {
  return fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      'Authorization': `Token ${apiToken}`,
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
}

// ---------- Settings / device setup ----------

async function initApp() {
  const config = await window.deviceConfig.get();
  if (!config || !config.apiBaseUrl || !config.token) {
    showView('settings'); // true first run — nothing saved yet, nothing to be offline-resilient about
    return;
  }
  apiBaseUrl = config.apiBaseUrl.replace(/\/$/, '');
  apiToken = config.token;

  // A device that's already configured must never be blocked from selling
  // just because it can't reach the server right now — enter the register
  // immediately with a cached attendant name, and refresh that name in the
  // background. This matters most exactly when it's hardest to notice:
  // an app restart or crash recovery mid-offline-session at a book fair.
  const cachedName = await window.localDb.getSyncMeta('attendant_name');
  $('attendant-name').textContent = cachedName || 'Attendant';
  showView('app');
  startBackgroundWork();

  try {
    const res = await apiFetch('/api/me/');
    if (res.ok) {
      const me = await res.json();
      const name = me.full_name || me.email;
      $('attendant-name').textContent = name;
      await window.localDb.setSyncMeta('attendant_name', name);
    }
  } catch (err) {
    // Offline at boot — fine, already in the register on cached data.
  }
}

$('settings-save').addEventListener('click', async () => {
  const urlInput = $('settings-api-url').value.trim().replace(/\/$/, '');
  const tokenInput = $('settings-token').value.trim();
  const errorEl = $('settings-error');
  errorEl.classList.add('hidden');

  const url = urlInput || apiBaseUrl;
  const token = tokenInput || apiToken;
  if (!url || !token) {
    errorEl.textContent = 'API URL and device token are both required.';
    errorEl.classList.remove('hidden');
    return;
  }

  try {
    const res = await fetch(`${url}/api/me/`, { headers: { Authorization: `Token ${token}` } });
    if (!res.ok) throw new Error(`Server responded ${res.status}. Check the URL and token.`);
    const me = await res.json();
    const name = me.full_name || me.email;
    await window.deviceConfig.set({ apiBaseUrl: url, token });
    apiBaseUrl = url;
    apiToken = token;
    $('attendant-name').textContent = name;
    await window.localDb.setSyncMeta('attendant_name', name);
    $('settings-token').value = '';
    showView('app');
    startBackgroundWork();
  } catch (err) {
    errorEl.textContent = `Could not connect: ${err.message}`;
    errorEl.classList.remove('hidden');
  }
});

$('settings-btn').addEventListener('click', () => {
  $('settings-api-url').value = apiBaseUrl || '';
  $('settings-token').value = '';
  $('settings-error').classList.add('hidden');
  // Already configured and mid-session — offer a way back without forcing
  // a reconnect (this device may just be offline right now, which is fine).
  $('settings-cancel').classList.toggle('hidden', !(apiBaseUrl && apiToken));
  showView('settings');
});

$('settings-cancel').addEventListener('click', () => showView('app'));

let backgroundWorkStarted = false;
function startBackgroundWork() {
  if (backgroundWorkStarted) return;
  backgroundWorkStarted = true;
  pullCatalog();
  scheduleSyncRetry(0);
  setInterval(pullCatalog, 60000);
  updateSyncPill();
}

// ---------- Sync indicator: connectivity + outbox depth ----------

async function updateSyncPill() {
  const pill = $('sync-pill');
  const label = $('sync-label');
  const online = navigator.onLine;
  const pendingCount = apiBaseUrl ? await window.localDb.getOutboxPendingCount() : 0;

  pill.classList.remove('sync-pill--online', 'sync-pill--offline', 'sync-pill--syncing');
  if (!online) {
    pill.classList.add('sync-pill--offline');
    label.textContent = pendingCount > 0 ? `Offline (${pendingCount} queued)` : 'Offline';
  } else if (pendingCount > 0) {
    pill.classList.add('sync-pill--syncing');
    label.textContent = `Syncing (${pendingCount})`;
  } else {
    pill.classList.add('sync-pill--online');
    label.textContent = 'Synced';
  }
}

window.addEventListener('online', () => {
  updateSyncPill();
  pullCatalog();
  syncBackoffMs = SYNC_BACKOFF_MIN;
  scheduleSyncRetry(0);
});
window.addEventListener('offline', updateSyncPill);

// ---------- Catalog pull (incremental, into the local SQLite mirror) ----------

async function pullCatalog() {
  if (!apiBaseUrl || !navigator.onLine) return;
  const since = await window.localDb.getSyncMeta('catalog_last_synced_at');
  const requestStartedAt = new Date().toISOString();
  try {
    const url = since ? `/api/catalog/?updated_since=${encodeURIComponent(since)}` : '/api/catalog/';
    const res = await apiFetch(url);
    if (!res.ok) return;
    const books = await res.json();
    if (books.length > 0) await window.localDb.upsertBooks(books);
    await window.localDb.setSyncMeta('catalog_last_synced_at', requestStartedAt);
    refreshAttendantNameIfNeeded();
  } catch (err) {
    // Offline or server unreachable — next periodic pull (or the 'online'
    // event) will retry. The local mirror just stays as fresh as it last was.
  }
}

async function refreshAttendantNameIfNeeded() {
  // The boot-time /api/me/ ping may have failed if we started up offline
  // (showing the "Attendant" placeholder) — a successful catalog pull means
  // we're online now, so it's a good moment to quietly fill in the real name.
  if ($('attendant-name').textContent !== 'Attendant') return;
  try {
    const res = await apiFetch('/api/me/');
    if (!res.ok) return;
    const me = await res.json();
    const name = me.full_name || me.email;
    $('attendant-name').textContent = name;
    await window.localDb.setSyncMeta('attendant_name', name);
  } catch (err) {
    // Try again on the next successful catalog pull.
  }
}

// ---------- Search / scan — live if online, local mirror fallback if not ----------

let searchDebounce = null;

$('search-input').addEventListener('keydown', async (e) => {
  if (e.key !== 'Enter') return;
  const code = e.target.value.trim();
  if (!code) return;
  $('scanner-state').textContent = 'LOOKING UP...';
  try {
    let book = null;
    let notFoundOnline = false;
    if (navigator.onLine) {
      try {
        const res = await apiFetch(`/api/catalog/lookup/?code=${encodeURIComponent(code)}`);
        if (res.ok) {
          book = await res.json();
        } else if (res.status === 404) {
          notFoundOnline = true;
        }
      } catch (networkErr) {
        // fall through to local lookup
      }
    }
    if (!book && !notFoundOnline) {
      book = await window.localDb.lookupLocalBook(code);
    }
    if (!book) {
      showError(`Scan failed: no book matches "${code}".`);
      return;
    }
    addToCart(book);
    e.target.value = '';
    $('search-results').innerHTML = '';
  } finally {
    $('scanner-state').textContent = 'READY';
  }
});

$('search-input').addEventListener('input', (e) => {
  clearTimeout(searchDebounce);
  const q = e.target.value.trim();
  if (q.length < 2) {
    $('search-results').innerHTML = '';
    return;
  }
  searchDebounce = setTimeout(() => runSearch(q), 250);
});

async function runSearch(q) {
  if (navigator.onLine) {
    try {
      const res = await apiFetch(`/api/catalog/?q=${encodeURIComponent(q)}`);
      if (res.ok) {
        renderSearchResults(await res.json());
        return;
      }
    } catch (err) {
      // fall through to local search
    }
  }
  const localResults = await window.localDb.searchLocalBooks(q);
  renderSearchResults(localResults);
}

function renderSearchResults(results) {
  const container = $('search-results');
  container.innerHTML = '';
  results.slice(0, 8).forEach((book) => {
    const div = document.createElement('div');
    div.className = 'search-result';
    div.dataset.outOfStock = book.stock_qty <= 0 ? 'true' : 'false';
    div.innerHTML = `
      <div>
        <div class="search-result__title">${escapeHtml(book.title)}</div>
        <div class="search-result__meta">${escapeHtml(book.author || '')} &middot; ${book.stock_qty} in stock</div>
      </div>
      <div class="search-result__price mono">${money(book.selling_price)}</div>
    `;
    div.addEventListener('click', () => {
      addToCart(book);
      $('search-input').value = '';
      container.innerHTML = '';
    });
    container.appendChild(div);
  });
}

// ---------- Cart ----------

function addToCart(book) {
  const existing = cart.find((i) => i.book_id === book.id);
  if (existing) {
    existing.qty += 1;
  } else {
    cart.push({
      book_id: book.id,
      title: book.title,
      author: book.author,
      unit_price: Number(book.selling_price),
      qty: 1,
      cover_image: book.cover_image,
      stock_qty: book.stock_qty,
    });
  }
  hideError();
  renderCart();
}

function renderCart() {
  const container = $('cart-items');
  if (cart.length === 0) {
    container.innerHTML = '<p class="empty-cart">Scan or search a book to begin.</p>';
  } else {
    container.innerHTML = '';
    cart.forEach((item) => {
      const div = document.createElement('div');
      div.className = 'cart-item';
      div.innerHTML = `
        <div class="cart-item__cover">${item.cover_image ? `<img src="${item.cover_image}">` : ''}</div>
        <div class="cart-item__info">
          <div class="cart-item__title">${escapeHtml(item.title)}</div>
          <div class="cart-item__author">${escapeHtml(item.author || '')}</div>
          <div class="cart-item__row">
            <div class="qty-control">
              <button data-action="dec">&minus;</button>
              <span>${item.qty}</span>
              <button data-action="inc">+</button>
            </div>
            <div>
              <span class="cart-item__price mono">${money(item.unit_price * item.qty)}</span>
              <button class="cart-item__remove" data-action="remove">Remove</button>
            </div>
          </div>
        </div>
      `;
      div.querySelector('[data-action="inc"]').addEventListener('click', () => {
        item.qty += 1;
        renderCart();
      });
      div.querySelector('[data-action="dec"]').addEventListener('click', () => {
        item.qty -= 1;
        if (item.qty <= 0) cart = cart.filter((i) => i !== item);
        renderCart();
      });
      div.querySelector('[data-action="remove"]').addEventListener('click', () => {
        cart = cart.filter((i) => i !== item);
        renderCart();
      });
      container.appendChild(div);
    });
  }
  const subtotal = cart.reduce((sum, i) => sum + i.unit_price * i.qty, 0);
  $('summary-subtotal').textContent = money(subtotal);
  $('summary-total').textContent = money(subtotal);
}

$('clear-cart').addEventListener('click', () => {
  if (cart.length === 0) return;
  cart = [];
  renderCart();
  hideError();
});

function showError(message) {
  const el = $('error-banner');
  el.textContent = message;
  el.classList.remove('hidden');
}
function hideError() {
  $('error-banner').classList.add('hidden');
}

// ---------- Loyalty — balance lookup + redemption at checkout ----------
// Read-only preview: the actual redemption is validated and applied
// server-side in create_sale() (never a second source of truth for
// discount math, same principle as the discounts already shown only after
// checkout). Requires being online to look up; offline, the section just
// stays hidden and no redemption is offered for that sale.

function resetLoyaltyUI() {
  loyaltyBalance = null;
  loyaltyPointValueGhs = 0;
  $('loyalty-section').classList.add('hidden');
  $('redeem-points').value = '0';
}

async function lookupLoyaltyBalance() {
  const phone = $('customer-phone').value.trim();
  if (!phone || !navigator.onLine) {
    resetLoyaltyUI();
    return;
  }
  try {
    const res = await apiFetch(`/api/customers/lookup/?phone=${encodeURIComponent(phone)}`);
    if (!res.ok) {
      resetLoyaltyUI();
      return;
    }
    const data = await res.json();
    loyaltyBalance = data.loyalty_points;
    loyaltyPointValueGhs = parseFloat(data.point_value_ghs) || 0;
    $('redeem-points').max = String(Math.max(loyaltyBalance, 0));
    $('redeem-points').value = '0';
    $('loyalty-balance-text').textContent =
      `${loyaltyBalance} point${loyaltyBalance === 1 ? '' : 's'} available` +
      (loyaltyBalance > 0 ? ` (worth ${money(loyaltyBalance * loyaltyPointValueGhs)})` : '');
    $('loyalty-section').classList.remove('hidden');
  } catch (err) {
    resetLoyaltyUI(); // offline in practice despite navigator.onLine, or a genuine network error — same fallback either way
  }
}

$('customer-phone').addEventListener('blur', lookupLoyaltyBalance);
$('redeem-points').addEventListener('input', () => {
  const input = $('redeem-points');
  const max = loyaltyBalance || 0;
  let value = parseInt(input.value, 10) || 0;
  value = Math.max(0, Math.min(value, max));
  input.value = String(value);
});

// ---------- Checkout — outbox first, always, then try for an authoritative receipt ----------

function setPaymentButtonsDisabled(disabled) {
  ['pay-cash', 'pay-momo', 'pay-card'].forEach((id) => { $(id).disabled = disabled; });
}

async function checkout(paymentMethod) {
  if (cart.length === 0) {
    showError('Add at least one item before taking payment.');
    return;
  }
  const phone = $('customer-phone').value.trim();
  if (!phone) {
    showError('Customer phone is required.');
    return;
  }

  hideError();
  setPaymentButtonsDisabled(true);

  const offlineUuid = crypto.randomUUID();
  const redeemPoints = parseInt($('redeem-points').value, 10) || 0;
  const payload = {
    channel: 'IN_STORE',
    items: cart.map((i) => ({ book_id: i.book_id, qty: i.qty })),
    payment_method: paymentMethod,
    offline_uuid: offlineUuid,
    customer_phone: phone,
    customer_full_name: $('customer-name').value.trim(),
    customer_email: $('customer-email').value.trim(),
    customer_birthday: $('customer-birthday').value || null,
    redeem_points: redeemPoints,
  };

  // Durability first — this write must happen before any network attempt,
  // online or not. A sale that made it here is real; losing it because the
  // network dropped mid-request is exactly the failure mode Phase 3 exists
  // to close off.
  await window.localDb.addToOutbox(offlineUuid, payload);
  for (const item of cart) {
    await window.localDb.adjustLocalStock(item.book_id, item.qty);
  }

  let serverSale = null;
  if (navigator.onLine) {
    try {
      const res = await apiFetch('/api/sales/', { method: 'POST', body: JSON.stringify(payload) });
      if (res.ok) {
        serverSale = await res.json();
        await window.localDb.markOutboxSynced(offlineUuid, serverSale);
      }
      // A non-ok response here (e.g. validation) is left PENDING in the
      // outbox; the batch sync worker will pick it up and surface it there
      // rather than blocking this attendant's receipt on it.
    } catch (networkErr) {
      // Offline in practice, even though navigator.onLine said otherwise —
      // fall through to the local receipt below.
    }
  }

  if (serverSale) {
    renderReceipt(serverSale, paymentMethod, false);
  } else {
    renderReceipt(buildLocalReceipt(payload, cart, offlineUuid), paymentMethod, true);
  }

  resetForNextTransaction();
  showReceiptView();
  setPaymentButtonsDisabled(false);
  updateSyncPill();
  scheduleSyncRetry(0);
}

$('pay-cash').addEventListener('click', () => checkout('CASH'));
$('pay-momo').addEventListener('click', () => checkout('MOMO'));
$('pay-card').addEventListener('click', () => checkout('CARD'));

function resetForNextTransaction() {
  cart = [];
  renderCart();
  $('customer-phone').value = '';
  $('customer-name').value = '';
  $('customer-email').value = '';
  $('customer-birthday').value = '';
  resetLoyaltyUI();
}

function buildLocalReceipt(payload, cartAtCheckout, offlineUuid) {
  // Discount computation is server-only, deliberately (never a second
  // source of truth for that logic) — an offline receipt shows subtotal as
  // the total and is clearly marked pending; discounts (if any) land once
  // this syncs.
  const items = cartAtCheckout.map((i) => ({
    title: i.title, author: i.author, qty: i.qty, unit_price: i.unit_price, line_discount: 0,
  }));
  const subtotal = items.reduce((sum, i) => sum + i.unit_price * i.qty, 0);
  return {
    id: null,
    offline_uuid: offlineUuid,
    items,
    subtotal,
    discount_amount: 0,
    total: subtotal,
    created_at: new Date().toISOString(),
  };
}

const PAYMENT_LABELS = { CASH: 'Cash', MOMO: 'Mobile Money', CARD: 'Card' };

function renderReceipt(sale, paymentMethod, pending) {
  const itemsHtml = sale.items.map((item) => `
    <div class="receipt-line">
      <div>
        <span class="item-title">${escapeHtml(item.title)}</span>
        <span class="item-meta">Qty: ${item.qty} @ ${money(item.unit_price)}</span>
      </div>
      <span class="mono">${money(item.qty * item.unit_price - item.line_discount)}</span>
    </div>
  `).join('');

  $('receipt-content').innerHTML = `
    ${pending ? `<div class="error-banner" style="margin-bottom: 1rem;">Recorded offline — will sync automatically once reconnected. Total may adjust for discounts.</div>` : ''}
    <div class="receipt-header">
      <h3>Book Pharm</h3>
      <p class="mono" style="font-size: 0.75rem;">${sale.id ? `Sale #${sale.id}` : 'Pending sync'} &middot; ${new Date(sale.created_at).toLocaleString()}</p>
    </div>
    <div>${itemsHtml}</div>
    <div class="receipt-summary">
      <div class="line"><span>Subtotal</span><span class="mono">${money(sale.subtotal)}</span></div>
      <div class="line"><span>Discount</span><span class="mono">-${money(sale.discount_amount)}</span></div>
      <div class="total"><span>Total</span><span>${money(sale.total)}</span></div>
    </div>
    <div class="receipt-payment">
      <div>Payment Method</div>
      <strong>${PAYMENT_LABELS[paymentMethod] || paymentMethod}</strong>
    </div>
    <div class="receipt-footer">Thank you for visiting Book Pharm.</div>
  `;
}

$('new-transaction').addEventListener('click', () => showView('app'));
$('print-receipt').addEventListener('click', () => window.print());

// ---------- Sync worker: drains the outbox, retries with backoff ----------

const SYNC_BACKOFF_MIN = 5000;
const SYNC_BACKOFF_MAX = 60000;
let syncBackoffMs = SYNC_BACKOFF_MIN;
let syncTimer = null;

function scheduleSyncRetry(delayMs) {
  clearTimeout(syncTimer);
  syncTimer = setTimeout(drainOutbox, delayMs === undefined ? syncBackoffMs : delayMs);
}

async function drainOutbox() {
  if (!apiBaseUrl) return; // not configured yet
  if (!navigator.onLine) {
    scheduleSyncRetry();
    return;
  }

  const pending = await window.localDb.getPendingOutbox();
  if (pending.length === 0) {
    syncBackoffMs = SYNC_BACKOFF_MIN;
    updateSyncPill();
    scheduleSyncRetry();
    return;
  }

  try {
    const res = await apiFetch('/api/sync/sales/', {
      method: 'POST',
      body: JSON.stringify({ sales: pending.map((p) => p.payload) }),
    });
    if (!res.ok) throw new Error(`Batch sync failed (${res.status})`);
    const body = await res.json();
    for (const result of body.results) {
      if (result.status === 'accepted') {
        await window.localDb.markOutboxSynced(result.offline_uuid, result.sale);
      } else {
        await window.localDb.markOutboxFailed(result.offline_uuid, result.error || 'Rejected by server');
      }
    }
    syncBackoffMs = SYNC_BACKOFF_MIN; // reset backoff after a successful round-trip
  } catch (err) {
    syncBackoffMs = Math.min(syncBackoffMs * 2, SYNC_BACKOFF_MAX);
  }

  updateSyncPill();
  scheduleSyncRetry();
}

// ---------- Boot ----------

updateSyncPill();
initApp();
