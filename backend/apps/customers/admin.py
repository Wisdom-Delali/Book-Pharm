from django.contrib import admin

from .models import Customer, LoyaltyProgram, LoyaltyTransaction


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone', 'email', 'birthday', 'loyalty_points', 'sms_opt_out', 'created_at']
    search_fields = ['full_name', 'phone', 'email']
    list_filter = ['sms_opt_out']


@admin.register(LoyaltyProgram)
class LoyaltyProgramAdmin(admin.ModelAdmin):
    list_display = ['points_per_ghs', 'point_value_ghs', 'min_redeem_points', 'is_active', 'updated_at']


@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ['customer', 'points', 'reason', 'sale', 'created_at']
    list_filter = ['reason']
    search_fields = ['customer__full_name', 'customer__phone']
