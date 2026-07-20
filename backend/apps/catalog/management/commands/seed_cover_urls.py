from django.core.management.base import BaseCommand

from apps.catalog.models import Book
from apps.catalog.placeholder_covers import placeholder_cover_url


class Command(BaseCommand):
    help = (
        'Backfill Book.cover_image_url with a placeholder URL (title text on a '
        'brand-palette background, see placeholder_covers.placeholder_cover_url) '
        'for any book that doesn\'t already have one. Safe to rerun — never '
        'overwrites a URL that\'s already set, whether from a prior run of this '
        'command or entered by hand in the portal.'
    )

    def handle(self, *args, **options):
        books = Book.objects.filter(cover_image_url='')
        updated = 0
        for book in books:
            book.cover_image_url = placeholder_cover_url(book.title)
            book.save(update_fields=['cover_image_url'])
            updated += 1
            self.stdout.write(f'  {book.title} -> {book.cover_image_url}')

        if updated:
            self.stdout.write(self.style.SUCCESS(f'Set cover_image_url on {updated} book(s).'))
        else:
            self.stdout.write('Every book already has a cover_image_url — nothing to do.')
