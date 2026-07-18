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

document.addEventListener('submit', (event) => {
  if (!event.target.matches('.js-add-to-cart-form')) return;
  event.preventDefault();
  handleAddToCart(event.target);
});

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.qty-stepper button[data-step]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = btn.parentElement.querySelector('input[name="qty"]');
      const step = parseInt(btn.dataset.step, 10);
      const min = parseInt(input.min || '1', 10);
      const max = parseInt(input.max || '99', 10);
      const next = (parseInt(input.value, 10) || min) + step;
      input.value = Math.min(max, Math.max(min, next));
    });
  });
});
