from django.contrib import admin

from .models import SmsCampaign, SmsLog


@admin.register(SmsCampaign)
class SmsCampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'audience', 'status', 'scheduled_for', 'sent_at', 'created_at']
    list_filter = ['status', 'audience']


@admin.register(SmsLog)
class SmsLogAdmin(admin.ModelAdmin):
    list_display = ['customer', 'campaign', 'status', 'sent_at']
    list_filter = ['status']
    search_fields = ['customer__full_name', 'customer__phone']
