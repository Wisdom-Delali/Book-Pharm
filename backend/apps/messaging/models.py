from django.db import models
from django.utils import timezone


class SmsCampaign(models.Model):
    class Audience(models.TextChoices):
        ALL = 'ALL', 'All customers'
        BIRTHDAY_TODAY = 'BIRTHDAY_TODAY', 'Birthdays today'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'

    name = models.CharField(max_length=150)
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.ALL)
    message = models.TextField(max_length=459, help_text='459 chars ≈ 3 SMS segments. Keep to 160 to stay a single segment.')
    scheduled_for = models.DateTimeField(null=True, blank=True, help_text='Leave blank to send on the next cron run.')
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def recipient_queryset(self):
        # Local import: apps.customers doesn't need to know messaging exists,
        # only the reverse.
        from apps.customers.models import Customer
        qs = Customer.objects.filter(sms_opt_out=False).exclude(phone='')
        if self.audience == self.Audience.BIRTHDAY_TODAY:
            today = timezone.localdate()
            qs = qs.filter(birthday__month=today.month, birthday__day=today.day)
        return qs


class SmsLog(models.Model):
    class Status(models.TextChoices):
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'

    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='sms_logs')
    # Nullable: birthday greetings aren't tied to a campaign (CLAUDE.md §6
    # lists SmsLog without a campaign FK; this is an addition, not a
    # deviation — without it there'd be no way to tell a campaign send from
    # a birthday send in the log).
    campaign = models.ForeignKey(SmsCampaign, null=True, blank=True, on_delete=models.SET_NULL, related_name='logs')
    message = models.TextField()
    provider_ref = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=6, choices=Status.choices)
    error = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f'{self.get_status_display()} to {self.customer} ({self.sent_at:%Y-%m-%d %H:%M})'
