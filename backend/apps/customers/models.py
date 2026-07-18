from decimal import Decimal

from django.db import models

from .phone import normalize_phone


class Customer(models.Model):
    phone = models.CharField(max_length=13, unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    birthday = models.DateField(null=True, blank=True)
    # Signed, not PositiveInteger: a redemption made while offline is
    # validated against a snapshot balance that may be stale by sync time
    # (same reasoning as Book.stock_qty, CLAUDE.md §7) — the sale already
    # happened and must never be rejected for it. See
    # apps/customers/services.py::redeem_points().
    loyalty_points = models.IntegerField(default=0)
    sms_opt_out = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['full_name', 'phone']

    def __str__(self):
        return self.full_name or self.phone

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)


class LoyaltyProgram(models.Model):
    """Owner-configurable loyalty rules (ROADMAP Phase 6: "Loyalty rules
    config in the portal"). Not in CLAUDE.md's original data model — that
    only specifies LoyaltyTransaction — but points accrual/redemption need a
    rate from *somewhere*, and hardcoding it would mean a code deploy every
    time the owner wants to change it. Modeled as a table (one active row
    expected) rather than a settings constant so she can edit it herself.
    """

    points_per_ghs = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal('1'),
        help_text='Points earned per GHS 1 spent (on the discounted book total, before delivery fee).',
    )
    point_value_ghs = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal('0.10'),
        help_text='GHS discount value of 1 point when redeemed.',
    )
    min_redeem_points = models.PositiveIntegerField(
        default=100, help_text='Minimum points a customer must redeem at once.',
    )
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Loyalty program settings'
        verbose_name_plural = 'Loyalty program settings'

    def __str__(self):
        return f'{self.points_per_ghs} pt/GHS earn, {self.point_value_ghs} GHS/pt redeem'

    @classmethod
    def current(cls):
        return cls.objects.filter(is_active=True).order_by('-updated_at').first()


class LoyaltyTransaction(models.Model):
    class Reason(models.TextChoices):
        SALE = 'SALE', 'Earned from purchase'
        REDEEM = 'REDEEM', 'Redeemed for discount'
        MANUAL = 'MANUAL', 'Manual adjustment'

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loyalty_transactions')
    points = models.IntegerField(help_text='Positive to award, negative to redeem/deduct.')
    reason = models.CharField(max_length=6, choices=Reason.choices)
    sale = models.ForeignKey(
        'sales.Sale', null=True, blank=True, on_delete=models.SET_NULL, related_name='loyalty_transactions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.points:+d} pts for {self.customer} ({self.reason})'
