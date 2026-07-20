from django.contrib import admin

from .forms import BookForm
from .models import Book, Category, PriceChangeLog, StockAdjustment, Tag
from .services import log_price_changes


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    # Reuses the portal's form so admin gets the same raw-ISBN-with-dashes
    # handling, and the same freeform get-or-create tags field, instead of
    # ModelAdmin's default machinery for each.
    form = BookForm
    list_display = ['title', 'author', 'isbn', 'internal_code', 'category', 'stock_qty', 'is_low_stock', 'is_active']
    list_filter = ['category', 'tags', 'is_active']
    search_fields = ['title', 'author', 'isbn', 'internal_code']

    @admin.display(boolean=True)
    def is_low_stock(self, obj):
        return obj.is_low_stock

    def save_model(self, request, obj, form, change):
        old_cost_price = old_selling_price = None
        if change:
            old_cost_price, old_selling_price = Book.objects.values_list(
                'cost_price', 'selling_price'
            ).get(pk=obj.pk)
        super().save_model(request, obj, form, change)
        if change:
            log_price_changes(obj, old_cost_price, old_selling_price, request.user)


@admin.register(PriceChangeLog)
class PriceChangeLogAdmin(admin.ModelAdmin):
    list_display = ['book', 'field', 'old_value', 'new_value', 'changed_by', 'changed_at']
    list_filter = ['field']
    readonly_fields = ['book', 'field', 'old_value', 'new_value', 'changed_by', 'changed_at']

    def has_add_permission(self, request):
        return False  # append-only log, written by log_price_changes()


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ['book', 'delta', 'resulting_qty', 'reason', 'adjusted_by', 'created_at']
    list_filter = ['reason']
    readonly_fields = ['created_at']
