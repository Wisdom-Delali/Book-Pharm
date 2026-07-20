from django.contrib import admin

from .forms import BookForm
from .models import Book, Category, StockAdjustment, Tag


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


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = ['book', 'delta', 'resulting_qty', 'reason', 'adjusted_by', 'created_at']
    list_filter = ['reason']
    readonly_fields = ['created_at']
