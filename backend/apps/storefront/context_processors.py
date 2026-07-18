from .cart import Cart


def cart_context(request):
    """So every storefront template can show the cart count in the header
    without each view having to remember to pass it."""
    return {'cart_count': len(Cart(request))}
