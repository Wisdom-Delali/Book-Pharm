from django.contrib import admin

from .models import DiscountRule, Sale, SaleItem, StockDiscrepancy


@admin.register(DiscountRule)
class DiscountRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'discount_type', 'value', 'scope', 'category', 'book', 'is_active']
    list_filter = ['scope', 'discount_type', 'is_active']


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['book', 'qty', 'unit_price', 'line_discount']


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['id', 'channel', 'customer', 'total', 'payment_method', 'payment_status', 'status', 'created_at']
    list_filter = ['channel', 'payment_method', 'payment_status', 'status']
    search_fields = ['id', 'offline_uuid', 'external_ref', 'customer__phone']
    inlines = [SaleItemInline]
    readonly_fields = ['offline_uuid', 'synced_at', 'created_at']


@admin.register(StockDiscrepancy)
class StockDiscrepancyAdmin(admin.ModelAdmin):
    list_display = ['book', 'stock_qty_after', 'sale_item', 'resolved', 'created_at']
    list_filter = ['resolved']
    readonly_fields = ['book', 'sale_item', 'stock_qty_after', 'created_at']
