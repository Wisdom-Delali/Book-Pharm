from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ShopLocation(models.Model):
    """Singleton (always pk=1, see load()) — the bookshop's own coordinates,
    the origin point for distance-based delivery pricing. Set once by the
    owner in the portal via the same Places Autocomplete picker used at
    checkout, so nobody has to look up raw coordinates by hand."""

    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.address or 'Shop location (not set)'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def is_configured(self):
        return self.latitude is not None and self.longitude is not None


class DeliveryPricingRule(models.Model):
    """Abstraction over delivery-fee methods (CLAUDE.md open item — now
    confirmed with the client, 2026-07-20: distance-based radius tiers from
    ShopLocation, chosen over per-km/linear pricing). radius_km is the
    upper bound of a ring around the shop — resolve_distance_fee() below
    picks the smallest ring a computed distance fits inside. Fixed zones
    remains supported (and is what checkout falls back to if no
    DISTANCE_BASED rules are configured); manual is modeled, not built."""

    class Method(models.TextChoices):
        FIXED_ZONE = 'FIXED_ZONE', 'Fixed Zone'
        DISTANCE_BASED = 'DISTANCE_BASED', 'Distance-based'
        MANUAL = 'MANUAL', 'Manual per order'

    method = models.CharField(max_length=14, choices=Method.choices, default=Method.FIXED_ZONE)
    zone_name = models.CharField(max_length=100, blank=True, help_text='FIXED_ZONE only, e.g. "Accra Central".')
    radius_km = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='DISTANCE_BASED only — upper bound of this ring, e.g. 2.00 for "up to 2km from the shop".',
    )
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['radius_km', 'zone_name']

    def __str__(self):
        if self.method == self.Method.FIXED_ZONE:
            return f'{self.zone_name}: GHS {self.fee}'
        if self.method == self.Method.DISTANCE_BASED:
            return f'Up to {self.radius_km}km: GHS {self.fee}'
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
    # Captured at checkout from Places Autocomplete / device geolocation —
    # the distance-pricing origin is ShopLocation, this is the destination.
    # Null for PICKUP, and for any DELIVERY address entered before this
    # existed or resolved without Maps configured.
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
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

    # Separate from rider_booked_*: this is standard DELIVERY dispatch (a
    # courier/boda-boda Book Pharm arranges itself) — the attendant types in
    # whoever's phone number for THIS delivery (no saved rider accounts) and
    # an SMS goes out with the order + a Google Maps link. RIDER_DELIVERY
    # (Yango/Bolt/Uber) is a completely different flow and never touches
    # these fields.
    delivery_rider_phone = models.CharField(max_length=20, blank=True)
    delivery_rider_sms_sent_at = models.DateTimeField(null=True, blank=True)
    delivery_rider_sms_sent_by = models.ForeignKey(
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
