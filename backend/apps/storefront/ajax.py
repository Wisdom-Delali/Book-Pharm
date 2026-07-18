def is_ajax(request):
    """Set explicitly by storefront.js on every fetch() call — nothing here
    relies on a browser-default header. Views that support both a JS and a
    no-JS fallback (e.g. cart_add) branch on this to return JSON instead of
    a redirect."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'
