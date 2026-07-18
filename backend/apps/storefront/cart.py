"""Session-based cart. No login required (SRS WEB-02) — lives entirely in
the Django session as {book_id_str: qty}, resolved against live Book rows
on every read so price/stock/availability are never stale."""

from decimal import Decimal

from apps.catalog.models import Book

SESSION_KEY = 'cart'


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(SESSION_KEY)
        if cart is None:
            cart = self.session[SESSION_KEY] = {}
        self.cart = cart

    def add(self, book_id, qty=1):
        key = str(book_id)
        self.cart[key] = self.cart.get(key, 0) + qty
        self._save()

    def set_qty(self, book_id, qty):
        key = str(book_id)
        if qty <= 0:
            self.cart.pop(key, None)
        else:
            self.cart[key] = qty
        self._save()

    def remove(self, book_id):
        key = str(book_id)
        if key in self.cart:
            del self.cart[key]
            self._save()

    def clear(self):
        self.session[SESSION_KEY] = {}
        self._save()

    def _save(self):
        self.session.modified = True

    def __len__(self):
        return sum(self.cart.values())

    def get_items(self):
        """[{'book': Book, 'qty': int, 'line_total': Decimal}] — silently
        drops books that were removed/deactivated since being added."""
        book_ids = [int(k) for k in self.cart.keys()]
        books = {b.id: b for b in Book.objects.filter(id__in=book_ids, is_active=True).select_related('category')}
        items = []
        for key, qty in self.cart.items():
            book = books.get(int(key))
            if book is None:
                continue
            items.append({'book': book, 'qty': qty, 'line_total': book.selling_price * qty})
        return items

    def subtotal(self):
        return sum((item['line_total'] for item in self.get_items()), Decimal('0'))
