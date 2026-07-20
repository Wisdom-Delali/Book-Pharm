from django.contrib import admin

from .models import DeliveryPricingRule, Fulfillment, Review, ShopLocation


@admin.register(ShopLocation)
class ShopLocationAdmin(admin.ModelAdmin):
    list_display = ['address', 'latitude', 'longitude', 'updated_at']

    def has_add_permission(self, request):
        # Singleton (ShopLocation.load(), always pk=1) — a second row would
        # just be dead data nothing reads.
        return not ShopLocation.objects.exists()


@admin.register(DeliveryPricingRule)
class DeliveryPricingRuleAdmin(admin.ModelAdmin):
    list_display = ['method', 'zone_name', 'radius_km', 'fee', 'is_active']
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
