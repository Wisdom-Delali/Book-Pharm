from django.core.management.base import BaseCommand

from apps.catalog.models import Book, Category
from apps.catalog.placeholder_covers import generate_placeholder_cover

CATEGORIES = ['Herbalism', 'Classical Lit', 'Alchemy', 'Medicine']

# A mix of books with real (checksum-valid) ISBNs and books with none, so the
# seed data exercises both the ISBN path and the internal-code generator.
BOOKS = [
    dict(title='Pharmacopoeia of Antiquity', author='Aurelius Vance', category='Medicine',
         isbn='978-3-16-148410-0', cost_price='85.00', selling_price='142.50', stock_qty=4, low_stock_threshold=5),
    dict(title="The Herbalist's Compendium", author='Flora Nightingale', category='Herbalism',
         isbn='978-0-26-251763-8', cost_price='34.20', selling_price='59.99', stock_qty=28, low_stock_threshold=5),
    dict(title='Principles of Alchemy', author='Isaac M. Thorne', category='Alchemy',
         isbn='978-1-59-327584-6', cost_price='112.00', selling_price='189.00', stock_qty=15, low_stock_threshold=5),
    dict(title='Ethical Foundations of Prose', author='S. G. Lawrence', category='Classical Lit',
         isbn='978-0-14-143951-8', cost_price='22.50', selling_price='45.00', stock_qty=2, low_stock_threshold=5),
    dict(title='Materia Medica: Vol II', author='Unknown', category='Medicine',
         isbn=None, cost_price='40.00', selling_price='75.00', stock_qty=3, low_stock_threshold=5),
    dict(title='Pharma Quarterly 2024', author='Editorial Collective', category='Medicine',
         isbn=None, cost_price='15.00', selling_price='25.00', stock_qty=5, low_stock_threshold=5),
    dict(title='Dried Herbs & Field Notes', author='Flora Nightingale', category='Herbalism',
         isbn=None, cost_price='18.00', selling_price='32.00', stock_qty=40, low_stock_threshold=8),
]


class Command(BaseCommand):
    help = 'Seed sample categories and books for local development.'

    def handle(self, *args, **options):
        categories = {}
        for name in CATEGORIES:
            category, created = Category.objects.get_or_create(name=name)
            categories[name] = category
            self.stdout.write(f'{"Created" if created else "Exists"} category: {name}')

        for data in BOOKS:
            category_name = data.pop('category')
            if Book.objects.filter(title=data['title']).exists():
                self.stdout.write(f'Exists book: {data["title"]}')
                continue
            book = Book.objects.create(category=categories[category_name], **data)
            code = book.isbn or book.internal_code
            self.stdout.write(self.style.SUCCESS(f'Created book: {book.title} ({code})'))

        # Every book without a cover gets a generated placeholder — not just
        # the ones listed above, so rows created ad hoc outside this script
        # (e.g. during manual testing) get one too. Safe to re-run: books
        # that already have a real cover are left untouched.
        for book in Book.objects.all():
            if book.cover_image:
                continue
            content = generate_placeholder_cover(book.title, book.author)
            book.cover_image.save(f'{book.slug or book.pk}.png', content, save=True)
            self.stdout.write(f'Generated placeholder cover: {book.title}')
