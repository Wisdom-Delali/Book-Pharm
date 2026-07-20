// Book Pharm storefront — toast notifications (WISDOM.md #10) and
// AJAX add-to-cart (no page reload). Everything else in the storefront is
// still plain form/redirect; this only touches the two things asked for.

function showToast(text, tags) {
  tags = tags || '';
  const variant = tags.indexOf('error') !== -1 ? 'error' : tags.indexOf('warning') !== -1 ? 'warning' : 'success';
  // No `style`/`backgroundColor` option here on purpose — Toastify applies
  // those as inline styles, which would out-specificity our own .toast--*
  // CSS. className is the only hook we pass it.
  Toastify({
    text: text,
    duration: 3500,
    close: true,
    gravity: 'top',
    position: 'right',
    stopOnFocus: true,
    className: 'toast toast--' + variant,
    escapeMarkup: true,
  }).showToast();
}
window.showToast = showToast;

function updateCartBadges(count) {
  document.querySelectorAll('.cart-badge').forEach((el) => {
    el.textContent = String(count);
    el.style.display = count > 0 ? '' : 'none';
  });
}

async function handleAddToCart(form) {
  const submitButtons = form.querySelectorAll('button[type="submit"]');
  const externalButtons = form.id
    ? document.querySelectorAll('button[form="' + form.id + '"]')
    : [];
  const allButtons = [...submitButtons, ...externalButtons];
  allButtons.forEach((btn) => { btn.disabled = true; });

  try {
    const res = await fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: new FormData(form),
    });
    if (!res.ok) throw new Error('request failed');
    const data = await res.json();
    showToast(data.message, 'success');
    updateCartBadges(data.cart_count);
    flashQuickAddButtons(allButtons);
    const qtyInput = form.querySelector('input[name="qty"]');
    if (qtyInput) qtyInput.value = '1';
  } catch (err) {
    showToast('Could not add that to your cart. Please try again.', 'error');
  } finally {
    allButtons.forEach((btn) => { btn.disabled = false; });
  }
}

function flashQuickAddButtons(buttons) {
  buttons.forEach((btn) => {
    const icon = btn.querySelector('.material-symbols-outlined');
    if (!icon) return; // the book-detail page's text "Add to Cart" button has no icon — toast alone is enough there
    const original = icon.textContent;
    icon.textContent = 'check';
    btn.classList.add('is-added');
    setTimeout(() => {
      icon.textContent = original;
      btn.classList.remove('is-added');
    }, 1200);
  });
}

// ---------- Cart page: quick +/- qty stepper + delete, both no-reload ----------
// (WISDOM.md #4) Unlike the book-detail page's stepper (adjusts the input,
// waits for an explicit "Add to Cart" click), a cart row's qty is already
// committed — "quick" here means each +/- click submits immediately, no
// separate confirm step. Typing an exact number and tabbing away submits
// the same way (the `change` listener below), so there's still a precise
// path for a large quantity without clicking + repeatedly.

function clampStep(input, step) {
  const min = parseInt(input.min || '1', 10);
  const max = parseInt(input.max || '99', 10);
  const current = parseInt(input.value, 10) || min;
  return Math.min(max, Math.max(min, current + step));
}

async function handleCartQtyUpdate(form) {
  const row = form.closest('.cart-row');
  const controls = form.querySelectorAll('button, input');
  controls.forEach((el) => { el.disabled = true; });

  try {
    const res = await fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: new FormData(form),
    });
    if (!res.ok) throw new Error('update failed');
    const data = await res.json();
    if (data.removed) {
      row.remove();
      if (!document.querySelector('.cart-row')) location.reload(); // last item — let the server render the empty-cart state
    } else {
      const totalEl = row.querySelector('.cart-row__total');
      if (totalEl) totalEl.textContent = 'GHS ' + data.line_total;
    }
    applyCartTotals(data);
  } catch (err) {
    showToast('Could not update quantity. Please try again.', 'error');
  } finally {
    controls.forEach((el) => { el.disabled = false; });
  }
}

async function handleCartRemove(form) {
  const row = form.closest('.cart-row');
  form.querySelectorAll('button').forEach((b) => { b.disabled = true; });
  try {
    const res = await fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: new FormData(form),
    });
    if (!res.ok) throw new Error('remove failed');
    const data = await res.json();
    row.remove();
    if (!document.querySelector('.cart-row')) location.reload();
    applyCartTotals(data);
  } catch (err) {
    showToast('Could not remove that item. Please try again.', 'error');
    form.querySelectorAll('button').forEach((b) => { b.disabled = false; });
  }
}

function applyCartTotals(data) {
  const subtotalEl = document.querySelector('.summary-total .value');
  if (subtotalEl && data.subtotal !== undefined) subtotalEl.textContent = 'GHS ' + data.subtotal;
  if (data.cart_count !== undefined) updateCartBadges(data.cart_count);
}

document.addEventListener('submit', (event) => {
  if (event.target.matches('.js-add-to-cart-form')) {
    event.preventDefault();
    handleAddToCart(event.target);
  } else if (event.target.matches('.js-cart-qty-form')) {
    event.preventDefault();
    handleCartQtyUpdate(event.target);
  } else if (event.target.matches('.js-cart-remove-form')) {
    event.preventDefault();
    handleCartRemove(event.target);
  }
});

document.addEventListener('change', (event) => {
  if (!event.target.matches('.js-cart-qty-form input[name="qty"]')) return;
  event.target.closest('form').requestSubmit();
});

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.qty-stepper button[data-step]').forEach((btn) => {
    const cartForm = btn.closest('.js-cart-qty-form');
    if (cartForm) {
      // Cart row: adjust, then submit immediately — see handleCartQtyUpdate.
      btn.addEventListener('click', () => {
        const input = cartForm.querySelector('input[name="qty"]');
        const next = clampStep(input, parseInt(btn.dataset.step, 10));
        if (next === parseInt(input.value, 10)) return;
        input.value = next;
        cartForm.requestSubmit();
      });
      return;
    }
    // Book-detail page: adjust only, "Add to Cart" is a separate click.
    btn.addEventListener('click', () => {
      const input = btn.parentElement.querySelector('input[name="qty"]');
      input.value = clampStep(input, parseInt(btn.dataset.step, 10));
    });
  });

  // Mobile search expand (WISDOM.md #8). No-op above the 900px breakpoint —
  // .is-open has no visual effect there (the input is already always
  // visible), but guarding on width avoids the icon glyph swapping to
  // "close" on desktop for no visible reason after a stray click.
  const searchForm = document.querySelector('.storefront-topbar__search');
  const searchToggle = document.querySelector('.storefront-topbar__search-toggle');
  if (searchForm && searchToggle) {
    const toggleIcon = searchToggle.querySelector('.material-symbols-outlined');
    searchToggle.addEventListener('click', () => {
      if (window.innerWidth > 900) return;
      const isOpen = searchForm.classList.toggle('is-open');
      toggleIcon.textContent = isOpen ? 'close' : 'search';
      if (isOpen) searchForm.querySelector('input').focus();
    });
  }
});

// New Arrivals (and any future) horizontal rail — click-to-scroll arrows.
document.addEventListener('click', (event) => {
  const btn = event.target.closest('[data-rail-scroll]');
  if (!btn) return;
  const rail = btn.parentElement.querySelector('.book-rail');
  if (!rail) return;
  rail.scrollBy({ left: parseInt(btn.dataset.railScroll, 10) * 320, behavior: 'smooth' });
});
