from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.utils.text import slugify

from .codes import generate_internal_code, normalize_isbn


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, blank=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class BookQuerySet(models.QuerySet):
    def low_stock(self):
        return self.filter(stock_qty__lte=models.F('low_stock_threshold'))


class Book(models.Model):
    isbn = models.CharField(max_length=13, unique=True, null=True, blank=True)
    internal_code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    # SEO-friendly storefront URLs (SRS WEB-08) — title-derived, id-suffixed
    # so two books with the same title never collide. Populated after the
    # first save, once a pk exists to suffix with.
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='books')
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    # Signed, not PositiveInteger: offline sync must allow this to go negative
    # on an oversell rather than reject a real sale (CLAUDE.md §7).
    stock_qty = models.IntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    cover_image = models.ImageField(upload_to='book_covers/', blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BookQuerySet.as_manager()

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    @property
    def is_low_stock(self):
        return self.stock_qty <= self.low_stock_threshold

    def clean(self):
        # Surfaces a clean form-validation error for a malformed ISBN.
        # save() below is the actual enforcement point for "isbn or a
        # generated internal_code" — it always ends up with one or the other.
        if self.isbn:
            self.isbn = normalize_isbn(self.isbn)

    def save(self, *args, **kwargs):
        if self.isbn:
            self.isbn = normalize_isbn(self.isbn)
        needs_generated_code = not self.isbn and not self.internal_code
        if not needs_generated_code:
            super().save(*args, **kwargs)
        else:
            attempts = 5
            for attempt in range(1, attempts + 1):
                self.internal_code = generate_internal_code()
                try:
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                    break
                except IntegrityError:
                    if attempt == attempts:
                        raise
        if not self.slug:
            self.slug = slugify(f'{self.title}-{self.pk}')[:255]
            super().save(update_fields=['slug'])


class StockAdjustment(models.Model):
    class Reason(models.TextChoices):
        RESTOCK = 'RESTOCK', 'Restock'
        CORRECTION = 'CORRECTION', 'Correction'
        DAMAGE = 'DAMAGE', 'Damage / loss'
        RETURN_TO_SUPPLIER = 'RETURN', 'Return to supplier'
        OTHER = 'OTHER', 'Other'

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='stock_adjustments')
    delta = models.IntegerField(help_text='Positive to add stock, negative to remove.')
    resulting_qty = models.IntegerField()
    reason = models.CharField(max_length=12, choices=Reason.choices)
    notes = models.CharField(max_length=255, blank=True)
    adjusted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='stock_adjustments'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.book} {self.delta:+d} ({self.reason})'
