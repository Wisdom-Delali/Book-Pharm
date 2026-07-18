"""Loyalty logic — kept out of apps/sales so that app doesn't need to know
loyalty's internal rules, per CLAUDE.md §9 ("if logic spans two apps, it
belongs in a service module"). apps/sales/services.py calls these at the
points where a sale becomes PAID / is created at the register.
"""

from decimal import Decimal

from django.db.models import F

from .models import Customer, LoyaltyProgram, LoyaltyTransaction


def award_points_for_sale(sale):
    """No-op without a customer or an active program — must never block or
    fail the sale itself, loyalty is a bonus on top of a completed sale."""
    if not sale.customer_id:
        return
    program = LoyaltyProgram.current()
    if not program:
        return
    earnable = sale.subtotal - sale.discount_amount
    points = int(earnable * program.points_per_ghs)
    if points <= 0:
        return
    LoyaltyTransaction.objects.create(
        customer_id=sale.customer_id, points=points, reason=LoyaltyTransaction.Reason.SALE, sale=sale,
    )
    Customer.objects.filter(pk=sale.customer_id).update(loyalty_points=F('loyalty_points') + points)


def resolve_redemption(customer, points, allow_oversell=False):
    """Returns (actual_points, discount_ghs) without mutating anything —
    called before the Sale row exists so a bad request fails before
    anything is written.

    allow_oversell=True is the offline-sync path: the attendant looked up
    the customer's balance while online and redeemed against that snapshot,
    which may be stale by the time this syncs. Unlike the connected path
    (which raises so the attendant can just pick a different amount), this
    never raises — it clamps to whatever's actually valid, down to 0
    (skipping the redemption but keeping the sale). A sale that already
    happened must never be permanently stuck retrying against a rejection
    that will never stop being true (CLAUDE.md §7's stock principle, applied
    the same way here) — raising on a fixed rule like min_redeem_points
    would do exactly that, since retrying the same request never changes
    the outcome the way a stock-count retry might.
    """
    if points <= 0:
        return 0, Decimal('0')
    if not customer:
        if allow_oversell:
            return 0, Decimal('0')
        raise ValueError('Redeeming points requires a customer.')

    program = LoyaltyProgram.current()
    if not program:
        if allow_oversell:
            return 0, Decimal('0')
        raise ValueError('Loyalty program is not configured.')

    if not allow_oversell:
        if points < program.min_redeem_points:
            raise ValueError(f'A minimum of {program.min_redeem_points} points is required to redeem.')
        if points > customer.loyalty_points:
            raise ValueError(f'{customer} only has {customer.loyalty_points} points available.')
        actual_points = points
    else:
        actual_points = min(points, max(customer.loyalty_points, 0))
        if actual_points < program.min_redeem_points:
            actual_points = 0

    if actual_points <= 0:
        return 0, Decimal('0')
    discount = (Decimal(actual_points) * program.point_value_ghs).quantize(Decimal('0.01'))
    return actual_points, discount


def apply_redemption(customer, points, sale):
    """The mutating half of a redemption — called only after the Sale row
    exists (with the actual_points resolve_redemption returned, not the
    originally-requested amount), so the ledger entry can reference it."""
    Customer.objects.filter(pk=customer.pk).update(loyalty_points=F('loyalty_points') - points)
    LoyaltyTransaction.objects.create(
        customer=customer, points=-points, reason=LoyaltyTransaction.Reason.REDEEM, sale=sale,
    )
