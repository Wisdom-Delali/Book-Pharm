from .distance import haversine_km
from .models import DeliveryPricingRule, ShopLocation


class DistanceOutOfRange(Exception):
    """Raised by resolve_distance_fee when a point is farther than every
    configured DISTANCE_BASED ring — standard Delivery isn't offered there
    (owner decision, 2026-07-20); the customer needs Pickup or Rider
    Delivery (Yango/Bolt/Uber) instead."""

    def __init__(self, distance_km):
        self.distance_km = distance_km
        super().__init__(f'No delivery ring covers {distance_km:.2f}km from the shop.')


def distance_pricing_available():
    """True only once the owner has actually configured this: a shop
    location AND at least one active DISTANCE_BASED ring. Checkout falls
    back to the fixed-zone dropdown otherwise, so a shop that hasn't set up
    radius pricing yet sees no behavior change at all."""
    shop = ShopLocation.load()
    return shop.is_configured and DeliveryPricingRule.objects.filter(
        method=DeliveryPricingRule.Method.DISTANCE_BASED, is_active=True,
    ).exists()


def resolve_distance_fee(latitude, longitude):
    """(fee, distance_km) for the smallest configured ring the point falls
    inside — e.g. rings at 1km/GHS20 and 2km/GHS25, a point 1.4km out
    resolves to the 2km ring. Raises DistanceOutOfRange past the largest
    ring. Callers must check distance_pricing_available() first; this
    doesn't fall back to fixed zones or anything else on its own."""
    shop = ShopLocation.load()
    distance_km = haversine_km(shop.latitude, shop.longitude, latitude, longitude)
    rule = DeliveryPricingRule.objects.filter(
        method=DeliveryPricingRule.Method.DISTANCE_BASED, is_active=True, radius_km__gte=distance_km,
    ).order_by('radius_km').first()
    if not rule:
        raise DistanceOutOfRange(distance_km)
    return rule.fee, distance_km
