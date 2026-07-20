from django.conf import settings

from apps.catalog.models import Category

from .cart import Cart


def cart_context(request):
    """So every storefront template can show the cart count in the header
    without each view having to remember to pass it."""
    return {'cart_count': len(Cart(request))}


def nav_context(request):
    """The sidebar/bottom-nav shell (templates/storefront/base.html) needs
    the category list on every storefront page, not just book_list — this
    avoids every view remembering to pass it."""
    return {'nav_categories': Category.objects.all()}


def google_maps_context(request):
    """Blank until the owner fills GOOGLE_MAPS_API_KEY into .env (never
    committed) — templates gate the Places Autocomplete / geolocation
    script on this being truthy, so an unconfigured key just means a plain
    text address field, not a broken page."""
    return {'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY}
