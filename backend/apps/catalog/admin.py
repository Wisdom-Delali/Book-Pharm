from django.contrib import admin

from .forms import BookForm
from .models import Book, Category, StockAdjustment


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    # Reuses the portal's form so admin gets the same raw-ISBN-with-dashes
    # handling instead of the model field's max_length=13 rejecting it
    # before normalization runs.
    form = BookForm
    list_display = ['title', 'author', 'isbn', 'internal_code', 'category', 'stock_qty', 'is_low_stock', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['title', 'author', 'isbn', 'internal_code']

    @admin.display(boolean=True)
    def is_low_stock(self, obj):
        return obj.is_low_stock


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ['book', 'delta', 'resulting_qty', 'reason', 'adjusted_by', 'created_at']
    list_filter = ['reason']
    readonly_fields = ['created_at']
