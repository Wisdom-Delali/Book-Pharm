"""Shared by any portal view that lets someone build a multi-book line-item
list via repeated book_id/qty form fields (the Alpine-driven rows pattern,
templates/portal/*/_form.html) — Jumia manual entry and the in-store
register both use this.
"""


def resolve_manual_items(request):
    """Repeated book_id/qty inputs -> the [{'book_id': int, 'qty': int}, ...]
    shape create_sale() expects. Blank rows (no book chosen) are silently
    dropped rather than treated as errors — the form always renders at
    least one row, and someone who adds a row and reconsiders shouldn't be
    forced to delete it."""
    book_ids = request.POST.getlist('book_id')
    qtys = request.POST.getlist('qty')
    items, errors = [], []
    for book_id_str, qty_str in zip(book_ids, qtys):
        if not book_id_str:
            continue
        try:
            qty = int(qty_str)
        except ValueError:
            errors.append('Quantity must be a whole number.')
            continue
        if qty < 1:
            errors.append('Quantity must be at least 1.')
            continue
        items.append({'book_id': int(book_id_str), 'qty': qty})
    return items, errors
