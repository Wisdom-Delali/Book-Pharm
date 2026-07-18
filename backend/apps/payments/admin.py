from django.contrib import admin

from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ['provider_ref', 'sale', 'provider', 'amount', 'status', 'created_at']
    list_filter = ['provider', 'status']
    search_fields = ['provider_ref']
    readonly_fields = ['raw_payload']
