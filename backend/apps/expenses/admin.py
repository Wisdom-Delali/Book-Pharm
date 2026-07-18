from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['date', 'category', 'amount', 'is_personal_withdrawal', 'created_by']
    list_filter = ['category', 'is_personal_withdrawal']
    search_fields = ['notes']
