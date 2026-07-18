from django.contrib import admin

from .models import DeliveryPricingRule, Fulfillment, Review


@admin.register(DeliveryPricingRule)
class DeliveryPricingRuleAdmin(admin.ModelAdmin):
    list_display = ['zone_name', 'method', 'fee', 'is_active']
    list_filter = ['method', 'is_active']


@admin.register(Fulfillment)
class FulfillmentAdmin(admin.ModelAdmin):
    list_display = ['sale', 'type', 'fee', 'status', 'needs_rider_booking']
    list_filter = ['type', 'status']
    readonly_fields = ['sale']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['sale', 'rating', 'created_at']
    list_filter = ['rating']
