"""Sale creation — the one place stock actually moves. Both the Phase 2
single-sale API and the Phase 3 offline-sync batch endpoint call this, so
their behavior (discounts, idempotency, stock handling) never diverges.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Book
from apps.customers.models import Customer
from apps.customers.phone import normalize_phone

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


@transaction.atomic
def create_sale(
    *, channel, items, payment_method, offline_uuid=None,
    customer_phone=None, customer_full_name='', customer_email='', customer_birthday=None,
    attendant=None, allow_oversell=False,
):
    """Returns (sale, created). If offline_uuid already exists, returns the
    existing sale with created=False — replaying a batch is a no-op
    (CLAUDE.md §7), and this covers accidental client retries too.

    allow_oversell=False (the default, used by the connected single-sale
    path) rejects a sale outright if stock is short — the device is online,
    so it can just check. Phase 3's offline batch sync calls this with
    allow_oversell=True: a sale that already happened at the register must
    never be silently discarded for going stock-negative.
    """
    if offline_uuid:
        existing = Sale.objects.filter(offline_uuid=offline_uuid).first()
        if existing:
            return existing, False

    if not items:
        raise ValueError('A sale must have at least one item.')

    customer = None
    if customer_phone:
        customer = _get_or_update_customer(customer_phone, customer_full_name, customer_email, customer_birthday)

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

    total = subtotal - discount_amount

    sale = Sale.objects.create(
        channel=channel,
        customer=customer,
        subtotal=subtotal,
        discount_amount=discount_amount,
        delivery_fee=Decimal('0'),
        total=total,
        payment_method=payment_method,
        payment_status=Sale.PaymentStatus.PAID,
        status=Sale.Status.COMPLETED,
        attendant=attendant,
        offline_uuid=offline_uuid,
        synced_at=timezone.now(),
    )

    for book, qty, unit_price, line_discount, unit_cost_price in resolved_items:
        sale_item = SaleItem.objects.create(
            sale=sale, book=book, qty=qty, unit_price=unit_price, line_discount=line_discount,
            unit_cost_price=unit_cost_price,
        )
        book.stock_qty -= qty
        book.save(update_fields=['stock_qty', 'updated_at'])
        # Whatever path got us here (should only be allow_oversell=True in
        # practice, since the checked path never lets this happen) — the
        # condition that matters is "stock is negative", not how it happened.
        if book.stock_qty < 0:
            StockDiscrepancy.objects.create(book=book, sale_item=sale_item, stock_qty_after=book.stock_qty)

    return sale, True
