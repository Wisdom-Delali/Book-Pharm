"""Haversine (straight-line) distance — chosen over a Distance Matrix API
call so distance-based delivery pricing needs no extra network round trip
at checkout, and "1km / 2km from the shop" reads as a literal radius, not
a driving route. Less accurate where a river/highway forces a longer real
route, but that trade-off was made deliberately (owner decision, 2026-07-20),
not by default.
"""
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = Decimal('6371')


def haversine_km(lat1, lon1, lat2, lon2) -> Decimal:
    lat1, lon1, lat2, lon2 = (radians(float(v)) for v in (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return EARTH_RADIUS_KM * Decimal(str(c))
