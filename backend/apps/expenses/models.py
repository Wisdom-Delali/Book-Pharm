from django.conf import settings
from django.db import models


class Expense(models.Model):
    class Category(models.TextChoices):
        RENT = 'RENT', 'Rent'
        UTILITIES = 'UTILITIES', 'Utilities'
        SUPPLIES = 'SUPPLIES', 'Supplies'
        INVENTORY = 'INVENTORY', 'Inventory purchase'
        SALARIES = 'SALARIES', 'Salaries'
        MARKETING = 'MARKETING', 'Marketing'
        TRANSPORT = 'TRANSPORT', 'Transport'
        MAINTENANCE = 'MAINTENANCE', 'Maintenance'
        PERSONAL = 'PERSONAL', 'Personal withdrawal'
        OTHER = 'OTHER', 'Other'

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=11, choices=Category.choices)
    # The single most important field on this model (CLAUDE.md §4): business
    # profit reports must exclude every row where this is True.
    is_personal_withdrawal = models.BooleanField(default=False)
    date = models.DateField()
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='expenses'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        kind = 'Personal' if self.is_personal_withdrawal else self.get_category_display()
        return f'{kind}: GHS {self.amount} ({self.date})'
