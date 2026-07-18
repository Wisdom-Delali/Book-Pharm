// Book Pharm POS — renderer logic. No Node/Electron APIs here except the
// narrow `window.deviceConfig` bridge exposed by preload.js; everything
// else (fetch, crypto.randomUUID, window.print) is standard web platform.

let apiBaseUrl = null;
let apiToken = null;
let cart = []; // [{ book_id, title, author, unit_price, qty, cover_image, stock_qty }]

const $ = (id) => document.getElementById(id);

function money(n) {
  return `GHS ${Number(n).toFixed(2)}`;
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
  const res = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers: {
      'Authorization': `Token ${apiToken}`,
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  return res;
}

// ---------- Settings / device setup ----------

async function initApp() {
  const config = await window.deviceConfig.get();
  if (!config || !config.apiBaseUrl || !config.token) {
    showView('settings');
    return;
  }
  apiBaseUrl = config.apiBaseUrl.replace(/\/$/, '');
  apiToken = config.token;

  try {
    const res = await apiFetch('/api/me/');
    if (!res.ok) throw new Error('Token rejected by server.');
    const me = await res.json();
    $('attendant-name').textContent = me.full_name || me.email;
    showView('app');
  } catch (err) {
    $('settings-error').textContent = `Could not connect: ${err.message}`;
    $('settings-error').classList.remove('hidden');
    $('settings-api-url').value = apiBaseUrl || '';
    showView('settings');
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
    await window.deviceConfig.set({ apiBaseUrl: url, token });
    apiBaseUrl = url;
    apiToken = token;
    $('attendant-name').textContent = me.full_name || me.email;
    $('settings-token').value = '';
    showView('app');
  } catch (err) {
    errorEl.textContent = `Could not connect: ${err.message}`;
    errorEl.classList.remove('hidden');
  }
});

$('settings-btn').addEventListener('click', () => {
  $('settings-api-url').value = apiBaseUrl || '';
  $('settings-token').value = '';
  $('settings-error').classList.add('hidden');
  showView('settings');
});

// ---------- Sync indicator (connectivity only — offline queueing is Phase 3) ----------

function updateSyncPill() {
  const pill = $('sync-pill');
  const label = $('sync-label');
  const online = navigator.onLine;
  pill.classList.toggle('sync-pill--online', online);
  pill.classList.toggle('sync-pill--offline', !online);
  label.textContent = online ? 'Online' : 'Offline';
}
window.addEventListener('online', updateSyncPill);
window.addEventListener('offline', updateSyncPill);

// ---------- Search / scan ----------

let searchDebounce = null;

$('search-input').addEventListener('keydown', async (e) => {
  if (e.key !== 'Enter') return;
  const code = e.target.value.trim();
  if (!code) return;
  $('scanner-state').textContent = 'LOOKING UP...';
  try {
    const res = await apiFetch(`/api/catalog/lookup/?code=${encodeURIComponent(code)}`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error || `Not found (${res.status})`);
    }
    const book = await res.json();
    addToCart(book);
    e.target.value = '';
    $('search-results').innerHTML = '';
  } catch (err) {
    showError(`Scan failed: ${err.message}`);
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
  try {
    const res = await apiFetch(`/api/catalog/?q=${encodeURIComponent(q)}`);
    if (!res.ok) return;
    const results = await res.json();
    renderSearchResults(results);
  } catch (err) {
    // Search-as-you-type failures are silent — the Enter-to-scan path is the
    // one that surfaces errors; a flaky keystroke-level fetch shouldn't nag.
  }
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

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
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

// ---------- Checkout ----------

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

  const payload = {
    channel: 'IN_STORE',
    items: cart.map((i) => ({ book_id: i.book_id, qty: i.qty })),
    payment_method: paymentMethod,
    offline_uuid: crypto.randomUUID(),
    customer_phone: phone,
    customer_full_name: $('customer-name').value.trim(),
    customer_email: $('customer-email').value.trim(),
    customer_birthday: $('customer-birthday').value || null,
  };

  try {
    const res = await apiFetch('/api/sales/', { method: 'POST', body: JSON.stringify(payload) });
    const body = await res.json();
    if (!res.ok) {
      throw new Error(body.error || `Sale failed (${res.status})`);
    }
    renderReceipt(body, paymentMethod);
    resetForNextTransaction();
    showReceiptView();
  } catch (err) {
    showError(err.message);
  } finally {
    setPaymentButtonsDisabled(false);
  }
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
}

const PAYMENT_LABELS = { CASH: 'Cash', MOMO: 'Mobile Money', CARD: 'Card' };

function renderReceipt(sale, paymentMethod) {
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
    <div class="receipt-header">
      <h3>Book Pharm</h3>
      <p class="mono" style="font-size: 0.75rem;">Sale #${sale.id} &middot; ${new Date(sale.created_at).toLocaleString()}</p>
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

// ---------- Boot ----------

updateSyncPill();
initApp();
