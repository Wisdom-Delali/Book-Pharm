from .models import PriceChangeLog


def log_price_changes(book, old_cost_price, old_selling_price, user):
    """Call after saving an edited Book, with prices captured *before* the
    save. old_cost_price/old_selling_price is None for a brand-new book
    (nothing to compare against — see PriceChangeLog's docstring)."""
    if old_cost_price is not None and old_cost_price != book.cost_price:
        PriceChangeLog.objects.create(
            book=book, field=PriceChangeLog.Field.COST_PRICE,
            old_value=old_cost_price, new_value=book.cost_price, changed_by=user,
        )
    if old_selling_price is not None and old_selling_price != book.selling_price:
        PriceChangeLog.objects.create(
            book=book, field=PriceChangeLog.Field.SELLING_PRICE,
            old_value=old_selling_price, new_value=book.selling_price, changed_by=user,
        )
