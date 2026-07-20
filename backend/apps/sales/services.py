"""Sale creation — the one place stock actually moves. The Phase 2
single-sale API, the Phase 3 offline-sync batch endpoint, and Phase 5's
online-checkout flow all end up here, so their behavior (discounts,
idempotency, stock handling) never diverges.

Online orders are two-phase, unlike POS/offline sales: payment is
asynchronous (redirect to Paystack, webhook arrives later), so stock can't
decrement at checkout time the way it does when cash changes hands at the
register. create_pending_online_sale() creates the Sale/SaleItems/Fulfillment
without touching stock; finalize_paid_sale() — called from both the
Paystack webhook and the verify-on-return view, idempotently — is the actual
stock-moving step, once payment is confirmed.
"""

import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Book
from apps.customers.models import Customer
from apps.customers.phone import normalize_phone
from apps.customers.services import apply_redemption, award_points_for_sale, resolve_redemption

from .models import DiscountRule, Sale, SaleItem, StockDiscrepancy


class InsufficientStockError(Exception):
    def __init__(self, book, requested, available):
        self.book = book
        self.requested = requested
        self.available = available
        super().__init__(f'Only {available} of "{book.title}" in stock, {requested} requested.')


def _best_discount_rule(book):
    """Most specific active rule wins: book-scoped > category-scoped > global."""
    rule = DiscountRule.objects.filter(is_active=True, scope=DiscountRule.Scope.BOOK, book=book).first()
    if rule:
        return rule
    rule = DiscountRule.objects.filter(
        is_active=True, scope=DiscountRule.Scope.CATEGORY, category=book.category
    ).first()
    if rule:
        return rule
    return DiscountRule.objects.filter(is_active=True, scope=DiscountRule.Scope.GLOBAL).first()


def _get_or_update_customer(phone, full_name, email, birthday):
    customer, _ = Customer.objects.get_or_create(
        phone=normalize_phone(phone),
        defaults={'full_name': full_name, 'email': email, 'birthday': birthday},
    )
    changed = False
    if full_name and not customer.full_name:
        customer.full_name = full_name
        changed = True
    if email and not customer.email:
        customer.email = email
        changed = True
    if birthday and not customer.birthday:
        customer.birthday = birthday
        changed = True
    if changed:
        customer.save()
    return customer


def _resolve_items(items, allow_oversell):
    """Locks and prices each requested book. Returns (subtotal,
    discount_amount, resolved_items) where resolved_items is
    [(book, qty, unit_price, line_discount, unit_cost_price), ...].
    Read-only beyond the row lock — no Sale/SaleItem/stock writes here."""
    if not items:
        raise ValueError('A sale must have at least one item.')

    book_ids = [item['book_id'] for item in items]
    books = {b.id: b for b in Book.objects.select_for_update().filter(id__in=book_ids)}

    subtotal = Decimal('0')
    discount_amount = Decimal('0')
    resolved_items = []
    for item in items:
        book = books.get(item['book_id'])
        if book is None:
            raise ValueError(f'Book {item["book_id"]} not found.')
        qty = item['qty']
        if not allow_oversell and book.stock_qty < qty:
            raise InsufficientStockError(book, qty, book.stock_qty)
        unit_price = book.selling_price
        line_subtotal = unit_price * qty
        rule = _best_discount_rule(book)
        line_discount = rule.discount_for(unit_price, qty) if rule else Decimal('0')
        subtotal += line_subtotal
        discount_amount += line_discount
        resolved_items.append((book, qty, unit_price, line_discount, book.cost_price))
    return subtotal, discount_amount, resolved_items


def _decrement_stock_for_item(book, qty, sale_item):
    book.stock_qty -= qty
    book.save(update_fields=['stock_qty', 'updated_at'])
    # Whatever path got us here — the condition that matters is "stock is
    # negative", not how it happened (CLAUDE.md §7).
    if book.stock_qty < 0:
        StockDiscrepancy.objects.create(book=book, sale_item=sale_item, stock_qty_after=book.stock_qty)


@transaction.atomic
def create_sale(
    *, channel, items, payment_method, offline_uuid=None,
    customer_phone=None, customer_full_name='', customer_email='', customer_birthday=None,
    attendant=None, allow_oversell=False, delivery_fee=Decimal('0'), redeem_points=0, external_ref='',
):
    """For payment-already-happened channels: POS (cash in hand) and offline
    sync (the sale already happened at the register, just arriving late).
    Not used for online checkout — see create_pending_online_sale() below.

    Returns (sale, created). If offline_uuid already exists, returns the
    existing sale with created=False — replaying a batch is a no-op
    (CLAUDE.md §7), and this covers accidental client retries too.

    allow_oversell=False (the default, used by the connected single-sale
    path) rejects a sale outright if stock is short — the device is online,
    so it can just check. Phase 3's offline batch sync calls this with
    allow_oversell=True: a sale that already happened at the register must
    never be silently discarded for going stock-negative. The same flag
    relaxes loyalty-point redemption the same way — see
    apps/customers/services.py::resolve_redemption().
    """
    if offline_uuid:
        existing = Sale.objects.filter(offline_uuid=offline_uuid).first()
        if existing:
            return existing, False

    customer = None
    if customer_phone:
        customer = _get_or_update_customer(customer_phone, customer_full_name, customer_email, customer_birthday)

    subtotal, discount_amount, resolved_items = _resolve_items(items, allow_oversell)

    # Resolved before the Sale row exists — same shape as the stock check
    # above. On the connected path a bad request fails clean; on the
    # offline-sync path it clamps instead (see resolve_redemption), so
    # actual_redeem_points may be less than what was requested, or 0.
    actual_redeem_points, redemption_discount = resolve_redemption(customer, redeem_points, allow_oversell=allow_oversell)
    if redemption_discount:
        discount_amount += redemption_discount

    total = subtotal - discount_amount + delivery_fee

    sale = Sale.objects.create(
        channel=channel,
        customer=customer,
        subtotal=subtotal,
        discount_amount=discount_amount,
        delivery_fee=delivery_fee,
        total=total,
        payment_method=payment_method,
        payment_status=Sale.PaymentStatus.PAID,
        status=Sale.Status.COMPLETED,
        attendant=attendant,
        offline_uuid=offline_uuid,
        synced_at=timezone.now(),
        external_ref=external_ref,
    )

    for book, qty, unit_price, line_discount, unit_cost_price in resolved_items:
        sale_item = SaleItem.objects.create(
            sale=sale, book=book, qty=qty, unit_price=unit_price, line_discount=line_discount,
            unit_cost_price=unit_cost_price,
        )
        _decrement_stock_for_item(book, qty, sale_item)

    if actual_redeem_points:
        apply_redemption(customer, actual_redeem_points, sale)
    award_points_for_sale(sale)

    return sale, True


@transaction.atomic
def create_pending_online_sale(
    *, items, customer_phone, customer_full_name='', customer_email='', customer_birthday=None,
    fulfillment_type, address='', delivery_fee=Decimal('0'), latitude=None, longitude=None,
):
    """Storefront checkout, before payment. Creates the Sale (PENDING),
    SaleItems, and Fulfillment — but does NOT touch stock. Checked
    (allow_oversell=False): unlike the register, there's no attendant to
    smooth over an out-of-stock surprise, so the customer should see it
    before being sent to pay, not after.

    A genuine race between this and finalize_paid_sale() (stock changes in
    between) is still possible — finalize_paid_sale() handles that the same
    way offline sync does: accept it, flag a discrepancy, never discard a
    sale that's already been paid for.
    """
    from apps.fulfillment.models import Fulfillment

    if not customer_phone:
        raise ValueError('Customer phone is required for online orders.')

    customer = _get_or_update_customer(customer_phone, customer_full_name, customer_email, customer_birthday)
    subtotal, discount_amount, resolved_items = _resolve_items(items, allow_oversell=False)
    total = subtotal - discount_amount + delivery_fee

    sale = Sale.objects.create(
        channel=Sale.Channel.ONLINE,
        customer=customer,
        subtotal=subtotal,
        discount_amount=discount_amount,
        delivery_fee=delivery_fee,
        total=total,
        payment_method='',
        payment_status=Sale.PaymentStatus.PENDING,
        status=Sale.Status.PENDING,
        # Doubles as the Paystack transaction reference.
        offline_uuid=uuid.uuid4(),
    )

    for book, qty, unit_price, line_discount, unit_cost_price in resolved_items:
        SaleItem.objects.create(
            sale=sale, book=book, qty=qty, unit_price=unit_price, line_discount=line_discount,
            unit_cost_price=unit_cost_price,
        )

    Fulfillment.objects.create(
        sale=sale, type=fulfillment_type, address=address, fee=delivery_fee,
        latitude=latitude, longitude=longitude,
    )

    return sale


@transaction.atomic
def finalize_paid_sale(sale, payment_method):
    """Called once Paystack confirms payment — from both the webhook and
    the verify-on-return view (CLAUDE.md §8: never trust the redirect
    alone). Idempotent: whichever fires first does the work, the second is
    a no-op, so there's no double stock decrement no matter which order
    they arrive in or if both fire.

    allow_oversell is implicitly True here: this sale has already been
    paid for. Refusing to honor it because stock moved in the meantime
    would lose money and data — same principle as offline sync (CLAUDE.md §7).
    """
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.payment_status == Sale.PaymentStatus.PAID:
        return sale

    sale_items = list(sale.items.select_related('book'))
    book_ids = [si.book_id for si in sale_items]
    books = {b.id: b for b in Book.objects.select_for_update().filter(id__in=book_ids)}
    for sale_item in sale_items:
        _decrement_stock_for_item(books[sale_item.book_id], sale_item.qty, sale_item)

    sale.payment_status = Sale.PaymentStatus.PAID
    sale.status = Sale.Status.COMPLETED
    sale.payment_method = payment_method
    sale.synced_at = timezone.now()
    sale.save(update_fields=['payment_status', 'status', 'payment_method', 'synced_at'])
    award_points_for_sale(sale)
    return sale


@transaction.atomic
def return_sale(sale):
    """Phase 7 (Jumia returns, CLAUDE.md §4): restores each line's stock and
    flips the sale to RETURNED. That status flip is what actually excludes
    it from revenue — apps/reports/views.py's sales/profit reports already
    filter on status=Sale.Status.COMPLETED, so a returned sale falls out of
    every revenue number for free, no separate reports-side exclusion
    needed. Channel-agnostic (nothing about the mechanics is Jumia-specific)
    even though the only caller today is the marketplace returns UI.
    Idempotent: returning an already-returned sale is a no-op rather than
    double-crediting stock back.
    """
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status == Sale.Status.RETURNED:
        return sale

    sale_items = list(sale.items.select_related('book'))
    book_ids = [si.book_id for si in sale_items]
    books = {b.id: b for b in Book.objects.select_for_update().filter(id__in=book_ids)}
    for sale_item in sale_items:
        book = books[sale_item.book_id]
        book.stock_qty += sale_item.qty
        book.save(update_fields=['stock_qty', 'updated_at'])

    sale.status = Sale.Status.RETURNED
    sale.returned_at = timezone.now()
    sale.save(update_fields=['status', 'returned_at'])
    return sale
