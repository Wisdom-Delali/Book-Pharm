// Book Pharm POS — renderer logic. No Node/Electron APIs here except the
// `window.deviceConfig`, `window.localDb`, and `window.printerApi` bridges
// exposed by preload.js; everything else (fetch, crypto.randomUUID,
// webContents.print via IPC) is standard web platform or those bridges.
// Offline sync design follows CLAUDE.md §7: every cash/card sale is written
// to the local outbox before anything else, online or offline alike, and
// the outbox is drained by a retrying background worker. MoMo sales
// (owner request, 2026-07-20) are online-only and never touch the outbox —
// see the "MoMo payment" section below.

let apiBaseUrl = null;
let apiToken = null;
let selectedPrinter = '';

// ---------- Multi-order register (owner request, 2026-07-20) ----------
// A second customer arriving mid-sale for the first must never lose the
// first customer's scanned items — so the register works on one of
// several concurrent "orders" (cart + customer fields + MoMo state each),
// switchable via tabs, rather than a single global cart. Exactly one order
// always exists; closing the last one resets it in place instead of
// leaving zero tabs.
let orders = [];
let activeOrderId = null;
let orderCounter = 0;
let momoPollTimer = null;

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
  $('view-login').classList.toggle('hidden', name !== 'login');
  $('view-app').classList.toggle('hidden', name !== 'app');
  $('view-settings').classList.toggle('hidden', name !== 'settings');
  if (name === 'app') showAppView('register');
}

// Register / My Day / Payments / Receipt are the sub-views inside the app
// shell (as opposed to showView, which switches between login/app/settings
// themselves). Tabs only make sense for register/myday/payments — a
// receipt isn't a tab destination, it's reached by checking out or by
// tapping a My Day/Payments row.
function showAppView(name) {
  $('view-register').classList.toggle('hidden', name !== 'register');
  $('view-myday').classList.toggle('hidden', name !== 'myday');
  $('view-payments').classList.toggle('hidden', name !== 'payments');
  $('view-receipt').classList.toggle('hidden', name !== 'receipt');
  $('tab-register').classList.toggle('is-active', name === 'register');
  $('tab-myday').classList.toggle('is-active', name === 'myday');
  $('tab-payments').classList.toggle('is-active', name === 'payments');
}

// Single entry point for putting a sale on screen as a receipt, whether
// it's the one just paid for or a past one opened from My Day — the two
// only differ in which follow-up actions make sense (fresh: New
// Transaction + the "sale recorded" banner; historical: Back to My Day,
// no banner) and whether the offline "will sync" notice applies.
function openReceipt(sale, paymentMethod, { pending = false, fresh = true } = {}) {
  renderReceipt(sale, paymentMethod, pending);
  $('receipt-success-banner').classList.toggle('hidden', !fresh);
  $('new-transaction').classList.toggle('hidden', !fresh);
  $('back-to-myday').classList.toggle('hidden', fresh);
  showAppView('receipt');
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

// ---------- Login (credentials) / Settings (printer only) ----------
// Split per owner request (2026-07-20): the gear icon, reachable only
// while signed in, used to also show URL/email/password fields for
// re-authenticating — now it's printer choice + Log Out only. Switching
// account or server means signing out first, same as most apps.

async function initApp() {
  const config = await window.deviceConfig.get();
  if (!config || !config.apiBaseUrl || !config.token) {
    showView('login'); // true first run — nothing saved yet, nothing to be offline-resilient about
    return;
  }
  apiBaseUrl = config.apiBaseUrl.replace(/\/$/, '');
  apiToken = config.token;
  selectedPrinter = config.printerName || '';

  // A device that's already configured must never be blocked from selling
  // just because it can't reach the server right now — enter the register
  // immediately with a cached attendant name, and refresh that name in the
  // background. This matters most exactly when it's hardest to notice:
  // an app restart or crash recovery mid-offline-session at a book fair.
  const cachedName = await window.localDb.getSyncMeta('attendant_name');
  $('attendant-name').textContent = cachedName || 'Attendant';
  ensureAtLeastOneOrder();
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

$('login-save').addEventListener('click', async () => {
  const urlInput = $('login-api-url').value.trim().replace(/\/$/, '');
  const email = $('login-email').value.trim();
  const password = $('login-password').value;
  const errorEl = $('login-error');
  errorEl.classList.add('hidden');

  if (!urlInput || !email || !password) {
    errorEl.textContent = 'API URL, email, and password are all required.';
    errorEl.classList.remove('hidden');
    return;
  }

  try {
    // Every attendant signs in with their own portal-created credentials —
    // the login endpoint hands back a token the same way regardless.
    const res = await fetch(`${urlInput}/api/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || `Server responded ${res.status}.`);
    const name = body.full_name || body.email;
    await window.deviceConfig.set({ apiBaseUrl: urlInput, token: body.token, printerName: selectedPrinter });
    apiBaseUrl = urlInput;
    apiToken = body.token;
    $('attendant-name').textContent = name;
    await window.localDb.setSyncMeta('attendant_name', name);
    $('login-password').value = '';
    ensureAtLeastOneOrder();
    showView('app');
    startBackgroundWork();
  } catch (err) {
    errorEl.textContent = `Could not sign in: ${err.message}`;
    errorEl.classList.remove('hidden');
  }
});

$('settings-btn').addEventListener('click', async () => {
  $('settings-error').classList.add('hidden');
  await loadPrinterOptions();
  showView('settings');
});

async function loadPrinterOptions() {
  const select = $('settings-printer');
  select.innerHTML = '<option value="">System default</option>';
  try {
    const printers = await window.printerApi.list();
    printers.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.name;
      opt.textContent = p.displayName + (p.isDefault ? ' (system default)' : '');
      select.appendChild(opt);
    });
    select.value = selectedPrinter || '';
  } catch (err) {
    $('settings-error').textContent = 'Could not list printers — the system default will be used.';
    $('settings-error').classList.remove('hidden');
  }
}

$('settings-save').addEventListener('click', async () => {
  selectedPrinter = $('settings-printer').value;
  const config = (await window.deviceConfig.get()) || {};
  await window.deviceConfig.set({ ...config, printerName: selectedPrinter });
  showView('app');
});

$('settings-cancel').addEventListener('click', () => showView('app'));

$('settings-logout').addEventListener('click', async () => {
  // Clears only the stored credentials — never the local outbox/catalog
  // mirror, which may hold sales that haven't synced yet (CLAUDE.md §7: a
  // sale is never lost, logging out the attendant who rang it up is not an
  // exception). The API URL is prefilled for the next sign-in as a
  // convenience — it's the shop's server address, not a secret.
  const lastUrl = apiBaseUrl;
  await window.deviceConfig.clear();
  apiBaseUrl = null;
  apiToken = null;
  $('login-api-url').value = lastUrl || '';
  $('login-email').value = '';
  $('login-password').value = '';
  showView('login');
});

let backgroundWorkStarted = false;
function startBackgroundWork() {
  if (backgroundWorkStarted) return;
  backgroundWorkStarted = true;
  pullCatalog();
  scheduleSyncRetry(0);
  setInterval(pullCatalog, 60000);
  updateSyncPill();
}

$('tab-register').addEventListener('click', () => showAppView('register'));
$('tab-myday').addEventListener('click', () => { showAppView('myday'); loadMyDay(); });
$('tab-payments').addEventListener('click', () => { showAppView('payments'); loadPayments(); });

// ---------- Sync indicator: connectivity + outbox depth ----------

async function updateSyncPill() {
  const pill = $('sync-pill');
  const label = $('sync-label');
  const countEl = $('sync-count');
  const online = navigator.onLine;
  const pendingCount = apiBaseUrl ? await window.localDb.getOutboxPendingCount() : 0;

  // The label already spells out "Offline (3 queued)" / "Syncing (3)", but
  // that's meant to be read; the count badge is meant to be *noticed* —
  // it's the thing that should register mid-sale without stopping to read.
  countEl.classList.toggle('hidden', pendingCount === 0);
  countEl.textContent = String(pendingCount);

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

  // MoMo needs a live connection to Paystack — cash/card stay fully
  // functional offline (outbox), so only this one button is gated.
  const momoBtn = $('pay-momo');
  if (momoBtn) {
    momoBtn.disabled = !online;
    momoBtn.title = online ? '' : 'Mobile Money needs a connection.';
  }
}

window.addEventListener('online', () => {
  updateSyncPill();
  pullCatalog();
  syncBackoffMs = SYNC_BACKOFF_MIN;
  scheduleSyncRetry(0);
});
window.addEventListener('offline', updateSyncPill);

$('sync-now-btn').addEventListener('click', () => {
  pullCatalog();
  syncBackoffMs = SYNC_BACKOFF_MIN;
  scheduleSyncRetry(0);
});

// ---------- Multi-order register ----------

function createOrder() {
  orderCounter += 1;
  return {
    id: `order-${orderCounter}`,
    label: `Order ${orderCounter}`,
    cart: [], // [{ book_id, title, author, unit_price, qty, cover_image, stock_qty }]
    customerPhone: '', customerName: '', customerEmail: '', customerBirthday: '',
    loyaltyBalance: null, loyaltyPointValueGhs: 0, redeemPoints: 0,
    // MoMo sub-state: 'idle' (not attempting) | 'pending' (prompt sent,
    // waiting) | 'failed' (Paystack said no / attendant cancelled).
    momoState: 'idle',
    momoPhone: '', momoProvider: 'mtn', momoOfflineUuid: null, momoError: '',
  };
}

function ensureAtLeastOneOrder() {
  if (orders.length === 0) {
    const order = createOrder();
    orders.push(order);
    activeOrderId = order.id;
  }
  renderOrderTabs();
  loadOrderIntoDOM(activeOrder());
}

function activeOrder() {
  return orders.find((o) => o.id === activeOrderId);
}

function saveActiveOrderFromDOM() {
  const order = activeOrder();
  if (!order) return;
  order.customerPhone = $('customer-phone').value;
  order.customerName = $('customer-name').value;
  order.customerEmail = $('customer-email').value;
  order.customerBirthday = $('customer-birthday').value;
  order.redeemPoints = parseInt($('redeem-points').value, 10) || 0;
}

function loadOrderIntoDOM(order) {
  $('customer-phone').value = order.customerPhone;
  $('customer-name').value = order.customerName;
  $('customer-email').value = order.customerEmail;
  $('customer-birthday').value = order.customerBirthday;
  $('redeem-points').value = String(order.redeemPoints || 0);
  hideError();
  renderCart();
  renderLoyaltyUI(order);
  renderMomoPanels(order);
}

function switchToOrder(id) {
  if (id === activeOrderId) return;
  saveActiveOrderFromDOM();
  activeOrderId = id;
  loadOrderIntoDOM(activeOrder());
  renderOrderTabs();
}

function addNewOrderTab() {
  saveActiveOrderFromDOM();
  const order = createOrder();
  orders.push(order);
  activeOrderId = order.id;
  loadOrderIntoDOM(order);
  renderOrderTabs();
}

function closeOrderTab(id) {
  const order = orders.find((o) => o.id === id);
  if (!order) return;
  if (order.momoState === 'pending') {
    showError('This order has a MoMo payment in progress — cancel the charge before closing it.');
    return;
  }
  if (orders.length === 1) {
    // Never zero tabs — reset the sole order in place instead of removing it.
    const fresh = createOrder();
    fresh.id = order.id;
    fresh.label = order.label;
    Object.assign(order, fresh);
    if (activeOrderId === id) loadOrderIntoDOM(order);
    renderOrderTabs();
    return;
  }
  const wasActive = activeOrderId === id;
  orders = orders.filter((o) => o.id !== id);
  if (wasActive) {
    activeOrderId = orders[0].id;
    loadOrderIntoDOM(activeOrder());
  }
  renderOrderTabs();
}

function renderOrderTabs() {
  const container = $('order-tabs');
  container.innerHTML = '';
  orders.forEach((order) => {
    const tab = document.createElement('div');
    tab.className = 'order-tab'
      + (order.id === activeOrderId ? ' is-active' : '')
      + (order.momoState === 'pending' ? ' is-pending' : '')
      + (order.momoState === 'failed' ? ' is-failed' : '');
    const itemCount = order.cart.reduce((n, i) => n + i.qty, 0);
    const select = document.createElement('button');
    select.type = 'button';
    select.className = 'order-tab__select';
    select.innerHTML = `${escapeHtml(order.label)}`
      + (itemCount ? ` <span class="order-tab__count">${itemCount}</span>` : '')
      + (order.momoState === 'pending' ? ' <span class="order-tab__spinner" title="Waiting for MoMo approval"></span>' : '')
      + (order.momoState === 'failed' ? ' <span class="order-tab__flag" title="MoMo payment failed">!</span>' : '');
    select.addEventListener('click', () => switchToOrder(order.id));
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'order-tab__close';
    close.setAttribute('aria-label', `Close ${order.label}`);
    close.innerHTML = '&times;';
    close.addEventListener('click', (e) => { e.stopPropagation(); closeOrderTab(order.id); });
    tab.appendChild(select);
    tab.appendChild(close);
    container.appendChild(tab);
  });
  const addBtn = document.createElement('button');
  addBtn.type = 'button';
  addBtn.className = 'order-tab__add';
  addBtn.textContent = '+ New Order';
  addBtn.addEventListener('click', addNewOrderTab);
  container.appendChild(addBtn);
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

// ---------- Cart (always the active order's cart) ----------

function addToCart(book) {
  const cart = activeOrder().cart;
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
  renderOrderTabs();
}

function renderCart() {
  const order = activeOrder();
  const cart = order.cart;
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
        renderOrderTabs();
      });
      div.querySelector('[data-action="dec"]').addEventListener('click', () => {
        item.qty -= 1;
        if (item.qty <= 0) order.cart = order.cart.filter((i) => i !== item);
        renderCart();
        renderOrderTabs();
      });
      div.querySelector('[data-action="remove"]').addEventListener('click', () => {
        order.cart = order.cart.filter((i) => i !== item);
        renderCart();
        renderOrderTabs();
      });
      container.appendChild(div);
    });
  }
  const subtotal = cart.reduce((sum, i) => sum + i.unit_price * i.qty, 0);
  $('summary-subtotal').textContent = money(subtotal);
  $('summary-total').textContent = money(subtotal);
}

$('clear-cart').addEventListener('click', () => {
  const order = activeOrder();
  if (order.cart.length === 0) return;
  order.cart = [];
  renderCart();
  renderOrderTabs();
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
// discount math). Requires being online to look up; offline, the section
// just stays hidden and no redemption is offered for that sale. Stored on
// the active order, not a global — each order previews its own customer's
// balance independently.

function resetLoyaltyUI(order) {
  order = order || activeOrder();
  order.loyaltyBalance = null;
  order.loyaltyPointValueGhs = 0;
  order.redeemPoints = 0;
  renderLoyaltyUI(order);
}

function renderLoyaltyUI(order) {
  if (order.loyaltyBalance === null) {
    $('loyalty-section').classList.add('hidden');
    $('redeem-points').value = '0';
    return;
  }
  $('redeem-points').max = String(Math.max(order.loyaltyBalance, 0));
  $('redeem-points').value = String(order.redeemPoints || 0);
  $('loyalty-balance-text').textContent =
    `${order.loyaltyBalance} point${order.loyaltyBalance === 1 ? '' : 's'} available` +
    (order.loyaltyBalance > 0 ? ` (worth ${money(order.loyaltyBalance * order.loyaltyPointValueGhs)})` : '');
  $('loyalty-section').classList.remove('hidden');
}

async function lookupLoyaltyBalance() {
  const order = activeOrder();
  const phone = $('customer-phone').value.trim();
  if (!phone || !navigator.onLine) {
    resetLoyaltyUI(order);
    return;
  }
  try {
    const res = await apiFetch(`/api/customers/lookup/?phone=${encodeURIComponent(phone)}`);
    if (!res.ok) {
      resetLoyaltyUI(order);
      return;
    }
    const data = await res.json();
    order.loyaltyBalance = data.loyalty_points;
    order.loyaltyPointValueGhs = parseFloat(data.point_value_ghs) || 0;
    order.redeemPoints = 0;
    renderLoyaltyUI(order);
  } catch (err) {
    resetLoyaltyUI(order); // offline in practice despite navigator.onLine, or a genuine network error — same fallback either way
  }
}

$('customer-phone').addEventListener('blur', lookupLoyaltyBalance);
$('redeem-points').addEventListener('input', () => {
  const order = activeOrder();
  const input = $('redeem-points');
  const max = order.loyaltyBalance || 0;
  let value = parseInt(input.value, 10) || 0;
  value = Math.max(0, Math.min(value, max));
  input.value = String(value);
  order.redeemPoints = value;
});

// ---------- Checkout: Cash / Card — outbox first, always ----------

function setPaymentButtonsDisabled(disabled) {
  ['pay-cash', 'pay-momo', 'pay-card'].forEach((id) => { $(id).disabled = disabled; });
  if (!disabled) updateSyncPill(); // re-applies the online-only gate on pay-momo
}

async function checkout(paymentMethod) {
  const order = activeOrder();
  if (order.cart.length === 0) {
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
  saveActiveOrderFromDOM();

  const offlineUuid = crypto.randomUUID();
  const payload = {
    channel: 'IN_STORE',
    items: order.cart.map((i) => ({ book_id: i.book_id, qty: i.qty })),
    payment_method: paymentMethod,
    offline_uuid: offlineUuid,
    customer_phone: order.customerPhone,
    customer_full_name: order.customerName,
    customer_email: order.customerEmail,
    customer_birthday: order.customerBirthday || null,
    redeem_points: order.redeemPoints,
  };

  // Durability first — this write must happen before any network attempt,
  // online or not. A sale that made it here is real; losing it because the
  // network dropped mid-request is exactly the failure mode Phase 3 exists
  // to close off.
  await window.localDb.addToOutbox(offlineUuid, payload);
  for (const item of order.cart) {
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

  const finishedSale = serverSale || buildLocalReceipt(payload, order.cart, offlineUuid);
  closeOrderTab(order.id); // this order is done — free its tab for reuse/removal
  openReceipt(finishedSale, paymentMethod, { pending: !serverSale, fresh: true });

  setPaymentButtonsDisabled(false);
  updateSyncPill();
  scheduleSyncRetry(0);
}

$('pay-cash').addEventListener('click', () => checkout('CASH'));
$('pay-card').addEventListener('click', () => checkout('CARD'));

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

$('new-transaction').addEventListener('click', () => showAppView('register'));
$('back-to-myday').addEventListener('click', () => { showAppView('myday'); loadMyDay(); });
$('print-receipt').addEventListener('click', printCurrentReceipt);

async function printCurrentReceipt() {
  // Always prefer the silent IPC path, even with no printer explicitly
  // chosen in Settings — deviceName: undefined resolves to the system
  // default on Electron's side, still silently. window.print()'s
  // interactive dialog is only the fallback if that path is unavailable or
  // itself fails; it is exactly what selecting a printer is meant to avoid
  // interrupting checkout with (see main.js's printer:print handler).
  if (window.printerApi) {
    try {
      const result = await window.printerApi.print({ deviceName: selectedPrinter || undefined });
      if (result && result.success) return;
    } catch (err) {
      // fall through
    }
  }
  window.print();
}

// ---------- MoMo payment (owner request, 2026-07-20) — Paystack direct
// charge, online-only. Unlike Cash/Card, the sale isn't paid the moment
// the attendant hits a button: it's created server-side as PENDING (stock
// untouched — owner decision: wait for Paystack confirmation, not the
// optimistic decrement Cash/Card use), a prompt goes to the customer's
// phone, and *this* device polls for the outcome — automatically while
// waiting, or via "Check Status" any time after. Never touches the local
// outbox: there is nothing to replay offline for a payment that only
// makes sense online. ----------

function showPaymentButtons(show) {
  $('payment-buttons').classList.toggle('hidden', !show);
}

function renderMomoPanels(order) {
  $('momo-form').classList.add('hidden'); // only ever shown by the pay-momo click below
  const showPending = order.momoState === 'pending' || order.momoState === 'failed';
  $('momo-pending').classList.toggle('hidden', !showPending);
  showPaymentButtons(!showPending);

  if (!showPending) return;
  const textEl = $('momo-pending-text');
  const errorEl = $('momo-pending-error');
  if (order.momoState === 'failed') {
    textEl.textContent = 'This charge did not succeed.';
    errorEl.textContent = order.momoError || 'Payment failed or was not approved in time.';
    errorEl.classList.remove('hidden');
    $('momo-cancel').textContent = 'Discard & Try Again';
  } else {
    textEl.textContent = "A payment prompt was sent — ask the customer to approve it on their phone.";
    errorEl.classList.add('hidden');
    $('momo-cancel').textContent = 'Cancel Charge';
  }
}

$('pay-momo').addEventListener('click', () => {
  const order = activeOrder();
  if (order.cart.length === 0) {
    showError('Add at least one item before taking payment.');
    return;
  }
  if (!$('customer-phone').value.trim()) {
    showError('Customer phone is required.');
    return;
  }
  saveActiveOrderFromDOM();
  hideError();
  $('momo-phone').value = order.momoPhone || order.customerPhone || '';
  $('momo-provider').value = order.momoProvider || 'mtn';
  $('momo-form-error').classList.add('hidden');
  showPaymentButtons(false);
  $('momo-form').classList.remove('hidden');
});

$('momo-form-cancel').addEventListener('click', () => {
  $('momo-form').classList.add('hidden');
  showPaymentButtons(true);
});

$('momo-send').addEventListener('click', async () => {
  const order = activeOrder();
  const momoPhone = $('momo-phone').value.trim();
  const momoProvider = $('momo-provider').value;
  const errorEl = $('momo-form-error');
  errorEl.classList.add('hidden');
  if (!momoPhone) {
    errorEl.textContent = "Enter the number to charge.";
    errorEl.classList.remove('hidden');
    return;
  }

  saveActiveOrderFromDOM();
  order.momoPhone = momoPhone;
  order.momoProvider = momoProvider;

  const sendBtn = $('momo-send');
  sendBtn.disabled = true;
  try {
    const res = await apiFetch('/api/sales/momo-charge/', {
      method: 'POST',
      body: JSON.stringify({
        items: order.cart.map((i) => ({ book_id: i.book_id, qty: i.qty })),
        customer_phone: order.customerPhone,
        customer_full_name: order.customerName,
        customer_email: order.customerEmail,
        customer_birthday: order.customerBirthday || null,
        momo_phone: momoPhone,
        momo_provider: momoProvider,
      }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || `Server responded ${res.status}.`);
    order.momoOfflineUuid = body.offline_uuid;
    order.momoState = 'pending';
    order.momoError = '';
    renderMomoPanels(order);
    renderOrderTabs();
    ensureMomoPolling();
  } catch (err) {
    errorEl.textContent = err.message || 'Could not reach the server.';
    errorEl.classList.remove('hidden');
  } finally {
    sendBtn.disabled = false;
  }
});

$('momo-check-status').addEventListener('click', () => checkMomoStatus(activeOrder(), { silent: false }));

$('momo-cancel').addEventListener('click', async () => {
  const order = activeOrder();
  const btn = $('momo-cancel');
  btn.disabled = true;
  try {
    if (order.momoOfflineUuid) {
      await apiFetch(`/api/sales/${order.momoOfflineUuid}/cancel/`, { method: 'POST' });
    }
  } catch (err) {
    // Best-effort — reset locally regardless so the attendant isn't stuck;
    // if this couldn't reach the server the sale just stays PENDING there
    // for the owner to notice on the Payments page.
  } finally {
    order.momoState = 'idle';
    order.momoOfflineUuid = null;
    order.momoError = '';
    renderMomoPanels(order);
    renderOrderTabs();
    btn.disabled = false;
  }
});

async function checkMomoStatus(order, { silent }) {
  if (!order || !order.momoOfflineUuid) return;
  if (!silent) {
    $('momo-check-status').disabled = true;
    $('momo-pending-error').classList.add('hidden');
  }
  try {
    const res = await apiFetch(`/api/payments/${order.momoOfflineUuid}/status/`);
    if (!res.ok) throw new Error(`Server responded ${res.status}.`);
    const sale = await res.json();

    if (sale.payment_status === 'PAID') {
      order.momoState = 'idle';
      const wasActive = order.id === activeOrderId;
      closeOrderTab(order.id); // free this tab — the sale is done
      if (wasActive) {
        openReceipt(sale, sale.payment_method, { pending: false, fresh: true });
      }
      // If it wasn't the active tab, resolving in the background is the
      // notification — no separate toast system exists in this app to
      // interrupt whatever order the attendant is currently ringing up.
    } else if (sale.status === 'CANCELLED') {
      order.momoState = 'failed';
      order.momoError = 'Payment failed or was not approved.';
      if (order.id === activeOrderId) renderMomoPanels(order);
      renderOrderTabs();
    }
    // else: still pending — nothing to do, keep waiting/polling.
  } catch (err) {
    if (!silent) {
      $('momo-pending-error').textContent = `Could not check status: ${err.message}`;
      $('momo-pending-error').classList.remove('hidden');
    }
  } finally {
    if (!silent) $('momo-check-status').disabled = false;
  }
}

function ensureMomoPolling() {
  if (momoPollTimer) return;
  momoPollTimer = setInterval(pollPendingMomoOrders, 5000);
}

function stopMomoPollingIfIdle() {
  if (orders.some((o) => o.momoState === 'pending')) return;
  clearInterval(momoPollTimer);
  momoPollTimer = null;
}

async function pollPendingMomoOrders() {
  const pending = orders.filter((o) => o.momoState === 'pending' && o.momoOfflineUuid);
  for (const order of pending) {
    await checkMomoStatus(order, { silent: true });
  }
  stopMomoPollingIfIdle();
}

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

// ---------- My Day: sales for one full day (default today), offline-aware,
// past receipts re-viewable. Merges the server's /api/sales/mine/
// (authoritative, cross-device — catches anything rung up on a different
// terminal that day) with this device's own local outbox — but only for
// *today*: a past day's outbox entries (if any were somehow still
// unsynced) aren't what this view is for, and the local mirror only ever
// tracks "today" regardless of which date is being reviewed. ----------

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

async function loadMyDay() {
  const picker = $('myday-date-picker');
  if (!picker.value) picker.value = todayIso();
  picker.max = todayIso(); // only full, already-happened days
  const dateStr = picker.value;

  $('myday-date').textContent = new Date(`${dateStr}T00:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });
  $('myday-list').innerHTML = '<tr><td colspan="5" class="empty-cart">Loading…</td></tr>';
  $('myday-summary').innerHTML = '';

  // Wrapped end-to-end, not just the network call: an exception anywhere in
  // here (IPC to the local DB included) must not leave the "Loading…"
  // placeholder stuck forever with no way to tell something went wrong.
  try {
    let serverSales = [];
    let reachedServer = false;
    if (apiBaseUrl && navigator.onLine) {
      try {
        const res = await apiFetch(`/api/sales/mine/?date=${encodeURIComponent(dateStr)}`);
        if (res.ok) {
          serverSales = await res.json();
          reachedServer = true;
        }
      } catch (err) {
        // Offline in practice — fall through to the local-only view below.
      }
    }

    const knownUuids = new Set(serverSales.map((s) => s.offline_uuid));
    const rows = serverSales.map((s) => ({ kind: 'sale', sale: s, at: s.created_at }));

    let pendingBooks = [];
    if (dateStr === todayIso()) {
      const todayOutbox = await window.localDb.getTodayOutbox();
      const pendingBookIds = new Set();
      for (const entry of todayOutbox) {
        if (knownUuids.has(entry.offline_uuid)) continue;
        if (entry.status === 'SYNCED' && entry.server_response) {
          rows.push({ kind: 'sale', sale: entry.server_response, at: entry.server_response.created_at || entry.created_at });
        } else {
          entry.payload.items.forEach((i) => pendingBookIds.add(i.book_id));
          rows.push({ kind: 'pending', entry, at: entry.created_at });
        }
      }
      pendingBooks = pendingBookIds.size ? await window.localDb.getBooksByIds([...pendingBookIds]) : [];
    }
    const bookById = new Map(pendingBooks.map((b) => [b.id, b]));

    rows.sort((a, b) => new Date(b.at) - new Date(a.at));
    renderMyDayList(rows, bookById, reachedServer);
  } catch (err) {
    $('myday-list').innerHTML = `<tr><td colspan="5" class="empty-cart">Couldn't load sales: ${escapeHtml(err.message)}</td></tr>`;
  }
}

$('myday-date-picker').addEventListener('change', loadMyDay);

function renderMyDayList(rows, bookById, reachedServer) {
  const completedSales = rows.filter((r) => r.kind === 'sale').map((r) => r.sale);
  const totalGhs = completedSales.reduce((sum, s) => sum + Number(s.total), 0);
  $('myday-summary').innerHTML = `
    <div class="myday-summary__stat"><span class="value">${completedSales.length}</span><span class="label">Sales</span></div>
    <div class="myday-summary__stat"><span class="value">${money(totalGhs)}</span><span class="label">Total</span></div>
    ${!reachedServer ? '<div class="myday-summary__stat"><span class="value">&mdash;</span><span class="label">Offline view (this device only)</span></div>' : ''}
  `;

  const tbody = $('myday-list');
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-cart">No sales this day.</td></tr>';
    return;
  }

  tbody.innerHTML = '';
  rows.forEach((row) => {
    const tr = document.createElement('tr');
    const time = new Date(row.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    if (row.kind === 'sale') {
      const s = row.sale;
      const itemCount = s.items.reduce((n, i) => n + i.qty, 0);
      tr.innerHTML = `
        <td>${time}</td>
        <td>${itemCount} item${itemCount === 1 ? '' : 's'}</td>
        <td>${PAYMENT_LABELS[s.payment_method] || s.payment_method}</td>
        <td class="text-right mono">${money(s.total)}</td>
        <td class="myday-table__actions"></td>
      `;
      const actions = tr.querySelector('.myday-table__actions');
      const viewBtn = document.createElement('button');
      viewBtn.type = 'button';
      viewBtn.className = 'secondary';
      viewBtn.textContent = 'View';
      viewBtn.addEventListener('click', () => openReceipt(s, s.payment_method, { pending: false, fresh: false }));
      const printBtn = document.createElement('button');
      printBtn.type = 'button';
      printBtn.className = 'secondary';
      printBtn.textContent = 'Print';
      printBtn.addEventListener('click', () => {
        openReceipt(s, s.payment_method, { pending: false, fresh: false });
        printCurrentReceipt();
      });
      actions.appendChild(viewBtn);
      actions.appendChild(printBtn);
    } else {
      // Not synced yet — only the raw checkout payload exists locally, so
      // there's no computed total/discount to show, and no receipt to open
      // until it syncs. Titles come from the catalog mirror since the
      // payload itself only has {book_id, qty}.
      const entry = row.entry;
      const itemCount = entry.payload.items.reduce((n, i) => n + i.qty, 0);
      const titles = entry.payload.items.map((i) => bookById.get(i.book_id)?.title).filter(Boolean);
      const itemsLabel = titles.length > 2
        ? `${titles.slice(0, 2).join(', ')} +${titles.length - 2} more`
        : (titles.join(', ') || `${itemCount} item${itemCount === 1 ? '' : 's'}`);
      tr.className = 'myday-row--pending';
      tr.innerHTML = `
        <td>${time}</td>
        <td>${escapeHtml(itemsLabel)}</td>
        <td colspan="2"><span class="myday-row__badge">Pending sync</span></td>
        <td></td>
      `;
    }
    tbody.appendChild(tr);
  });
}

// ---------- Payments: every MoMo attempt on any device (owner request,
// 2026-07-20) — not scoped to whoever's signed in here, since a charge one
// attendant started may need someone else to notice or retry it. ----------

const PAYMENT_STATUS_LABELS = { PENDING: 'Pending', SUCCESS: 'Success', FAILED: 'Failed', ABANDONED: 'Abandoned' };

$('payments-refresh').addEventListener('click', loadPayments);

async function loadPayments() {
  const tbody = $('payments-list');
  tbody.innerHTML = '<tr><td colspan="6" class="empty-cart">Loading…</td></tr>';
  if (!apiBaseUrl || !navigator.onLine) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-cart">Payments need a connection to load.</td></tr>';
    return;
  }
  try {
    const res = await apiFetch('/api/payments/in-store/');
    if (!res.ok) throw new Error(`Server responded ${res.status}.`);
    renderPaymentsList(await res.json());
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-cart">Couldn't load payments: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderPaymentsList(rows) {
  const tbody = $('payments-list');
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-cart">No MoMo payments yet.</td></tr>';
    return;
  }
  tbody.innerHTML = '';
  rows.forEach((txn) => {
    const tr = document.createElement('tr');
    const when = new Date(txn.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    tr.innerHTML = `
      <td>${when}</td>
      <td>${escapeHtml(txn.customer_full_name || txn.customer_phone || '—')}</td>
      <td>${escapeHtml(txn.attendant_name || '—')}</td>
      <td class="text-right mono">${money(txn.amount)}</td>
      <td><span class="payment-status payment-status--${txn.status.toLowerCase()}">${PAYMENT_STATUS_LABELS[txn.status] || txn.status}</span></td>
      <td class="myday-table__actions"></td>
    `;
    if (txn.status === 'PENDING') {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'secondary';
      btn.textContent = 'Check Status';
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        btn.textContent = 'Checking…';
        try {
          await apiFetch(`/api/payments/${txn.offline_uuid}/status/`);
        } catch (err) {
          // best-effort — loadPayments() below reflects whatever the
          // server actually knows either way
        }
        loadPayments();
      });
      tr.querySelector('.myday-table__actions').appendChild(btn);
    }
    tbody.appendChild(tr);
  });
}

// ---------- Sync worker: drains the outbox, retries with backoff ----------
// Cash/Card only — MoMo sales never touch the outbox (see the MoMo section
// above), so this worker has nothing to do with them either way.

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
