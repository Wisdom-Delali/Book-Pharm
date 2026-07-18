from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class DeliveryPricingRule(models.Model):
    """Abstraction over delivery-fee methods (CLAUDE.md open item — method
    still unconfirmed with the client). Fixed zones is the only method that
    actually computes a fee today; distance-based and manual are modeled so
    they can drop in later without a schema change, not implemented."""

    class Method(models.TextChoices):
        FIXED_ZONE = 'FIXED_ZONE', 'Fixed Zone'
        DISTANCE_BASED = 'DISTANCE_BASED', 'Distance-based'
        MANUAL = 'MANUAL', 'Manual per order'

    method = models.CharField(max_length=14, choices=Method.choices, default=Method.FIXED_ZONE)
    zone_name = models.CharField(max_length=100, blank=True, help_text='FIXED_ZONE only, e.g. "Accra Central".')
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    per_km_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    base_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['zone_name']

    def __str__(self):
        if self.method == self.Method.FIXED_ZONE:
            return f'{self.zone_name}: GHS {self.fee}'
        return self.get_method_display()


class Fulfillment(models.Model):
    class Type(models.TextChoices):
        DELIVERY = 'DELIVERY', 'Delivery'
        PICKUP = 'PICKUP', 'Pickup'
        # Owner request 2026-07-18, not part of the original questionnaire —
        # see CLAUDE.md §4/§6 and docs/discovery.md. No fee is ever
        # calculated for this: Book Pharm charges for the books only, and
        # the attendant books the actual ride separately.
        RIDER_DELIVERY = 'RIDER_DELIVERY', 'Yango / Bolt / Uber Delivery'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        READY = 'READY', 'Ready'
        COMPLETED = 'COMPLETED', 'Completed'

    sale = models.OneToOneField('sales.Sale', on_delete=models.CASCADE, related_name='fulfillment')
    type = models.CharField(max_length=14, choices=Type.choices)
    address = models.CharField(max_length=255, blank=True)
    pricing_rule = models.ForeignKey(
        DeliveryPricingRule, null=True, blank=True, on_delete=models.SET_NULL, related_name='fulfillments'
    )
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    confirmed_by_customer_at = models.DateTimeField(null=True, blank=True)

    # Rider-delivery booking tracking — the actionable flag from CLAUDE.md §4
    # ("the portal must flag rider-delivery orders as needing a booking
    # until the attendant marks one placed"). Irrelevant for DELIVERY/PICKUP.
    rider_booked_at = models.DateTimeField(null=True, blank=True)
    rider_booked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.get_type_display()} for Sale #{self.sale_id}'

    def clean(self):
        if self.type in (self.Type.DELIVERY, self.Type.RIDER_DELIVERY) and not self.address:
            raise ValidationError('Address is required for delivery and rider-delivery orders.')

    @property
    def needs_rider_booking(self):
        return self.type == self.Type.RIDER_DELIVERY and self.rider_booked_at is None


class Review(models.Model):
    sale = models.ForeignKey('sales.Sale', on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.rating}★ on Sale #{self.sale_id}'

    def clean(self):
        if not (1 <= self.rating <= 5):
            raise ValidationError('Rating must be between 1 and 5.')
