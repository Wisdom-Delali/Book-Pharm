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
