from django.db import models


class PaymentTransaction(models.Model):
    class Provider(models.TextChoices):
        PAYSTACK = 'PAYSTACK', 'Paystack'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'
        ABANDONED = 'ABANDONED', 'Abandoned'

    sale = models.ForeignKey('sales.Sale', on_delete=models.CASCADE, related_name='payment_transactions')
    provider = models.CharField(max_length=10, choices=Provider.choices, default=Provider.PAYSTACK)
    # Same value as Sale.offline_uuid, as a string — Paystack's transaction
    # reference. Using one shared identifier lets the webhook/verify-on-return
    # handlers look the pending Sale straight up, no separate mapping table.
    provider_ref = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    # The client has been burned before by payments not reflecting (CLAUDE.md
    # §8) — store the full gateway payload on every transaction, always.
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.provider_ref} ({self.status})'
