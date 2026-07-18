from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class DiscountRule(models.Model):
    class DiscountType(models.TextChoices):
        PERCENT = 'PERCENT', 'Percentage'
        FIXED = 'FIXED', 'Fixed amount'

    class Scope(models.TextChoices):
        GLOBAL = 'GLOBAL', 'Global'
        CATEGORY = 'CATEGORY', 'Category'
        BOOK = 'BOOK', 'Book'

    class ApprovalLevel(models.TextChoices):
        OWNER = 'OWNER', 'Owner only'
        STAFF = 'STAFF', 'Staff within limit'

    name = models.CharField(max_length=100)
    discount_type = models.CharField(max_length=7, choices=DiscountType.choices)
    value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text='Percent (0-100) for PERCENT, or a GHS amount per unit for FIXED.',
    )
    scope = models.CharField(max_length=8, choices=Scope.choices, default=Scope.GLOBAL)
    # FKs rather than CLAUDE.md's generic "target" field — a real reference
    # is safer than a loose integer id with no referential integrity.
    category = models.ForeignKey(
        'catalog.Category', null=True, blank=True, on_delete=models.CASCADE, related_name='discount_rules'
    )
    book = models.ForeignKey(
        'catalog.Book', null=True, blank=True, on_delete=models.CASCADE, related_name='discount_rules'
    )
    # Modeled per CLAUDE.md's open item; not enforced yet — single owner login today.
    approval_level = models.CharField(max_length=5, choices=ApprovalLevel.choices, default=ApprovalLevel.OWNER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def clean(self):
        if self.scope == self.Scope.CATEGORY and not self.category_id:
            raise ValidationError('Category is required when scope is Category.')
        if self.scope == self.Scope.BOOK and not self.book_id:
            raise ValidationError('Book is required when scope is Book.')
        if self.discount_type == self.DiscountType.PERCENT and not (0 < self.value <= 100):
            raise ValidationError('Percentage discounts must be greater than 0 and at most 100.')

    def discount_for(self, unit_price, qty):
        """Discount amount for a line of `qty` units at `unit_price` each,
        capped so a line can never go negative."""
        line_subtotal = unit_price * qty
        if self.discount_type == self.DiscountType.PERCENT:
            amount = line_subtotal * self.value / Decimal('100')
        else:
            amount = self.value * qty
        return min(amount, line_subtotal)


class Sale(models.Model):
    class Channel(models.TextChoices):
        IN_STORE = 'IN_STORE', 'In-store'
        ONLINE = 'ONLINE', 'Online'
        JUMIA = 'JUMIA', 'Jumia'

    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'Cash'
        MOMO = 'MOMO', 'Mobile Money'
        CARD = 'CARD', 'Card'
        BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'

    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PAID = 'PAID', 'Paid'
        FAILED = 'FAILED', 'Failed'
        REFUNDED = 'REFUNDED', 'Refunded'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        RETURNED = 'RETURNED', 'Returned'

    channel = models.CharField(max_length=8, choices=Channel.choices)
    customer = models.ForeignKey(
        'customers.Customer', null=True, blank=True, on_delete=models.SET_NULL, related_name='sales'
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    total = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=13, choices=PaymentMethod.choices)
    payment_status = models.CharField(max_length=8, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.PENDING)
    attendant = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='sales'
    )
    # Client-generated, online or offline (CLAUDE.md §7) — the idempotency key.
    offline_uuid = models.UUIDField(unique=True, null=True, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)
    external_ref = models.CharField(max_length=100, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Sale #{self.pk} ({self.get_channel_display()})'


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    # PROTECT, not CASCADE: a book must never be hard-deleted out from under
    # sale history. Deactivate via Book.is_active instead.
    book = models.ForeignKey('catalog.Book', on_delete=models.PROTECT, related_name='sale_items')
    qty = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))

    def __str__(self):
        return f'{self.qty} x {self.book} (Sale #{self.sale_id})'

    @property
    def line_total(self):
        return self.unit_price * self.qty - self.line_discount
