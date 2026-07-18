"""cPanel cron target — see docs/deployment.md. Runs once daily. Not routed
through SmsCampaign: campaigns are one-shot (DRAFT -> SCHEDULED -> SENT),
birthdays are an every-day-forever check against Customer.birthday, which
doesn't fit that lifecycle.

Dedup guard: an SmsLog with campaign=None already means "birthday send" in
this codebase (campaigns always set one) — so "already has one today" is a
reliable idempotency check if the cron fires twice or is re-run by hand.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.customers.models import Customer
from apps.messaging.models import SmsLog
from apps.messaging.sms_client import SmsError, send_sms


class Command(BaseCommand):
    help = "Send a birthday greeting SMS to every customer whose birthday is today."

    def handle(self, *args, **options):
        if not settings.SMSONLINEGH_API_KEY:
            self.stderr.write(self.style.WARNING('SMSONLINEGH_API_KEY is not configured — skipping this run.'))
            return

        today = timezone.localdate()
        already_sent_ids = set(
            SmsLog.objects.filter(
                campaign__isnull=True, status=SmsLog.Status.SENT, sent_at__date=today,
            ).values_list('customer_id', flat=True)
        )

        customers = Customer.objects.filter(
            birthday__month=today.month, birthday__day=today.day, sms_opt_out=False,
        ).exclude(phone='').exclude(pk__in=already_sent_ids)

        if not customers.exists():
            self.stdout.write('No birthdays today (or all already sent).')
            return

        sent = failed = 0
        for customer in customers:
            first_name = customer.full_name.split()[0] if customer.full_name else ''
            message = settings.BIRTHDAY_SMS_MESSAGE.format(name_suffix=f', {first_name}' if first_name else '')
            try:
                ref = send_sms(to=customer.phone, message=message)
                SmsLog.objects.create(customer=customer, message=message, provider_ref=ref, status=SmsLog.Status.SENT)
                sent += 1
            except SmsError as exc:
                SmsLog.objects.create(customer=customer, message=message, status=SmsLog.Status.FAILED, error=str(exc)[:255])
                failed += 1

        self.stdout.write(self.style.SUCCESS(f'Birthdays: {sent} sent, {failed} failed.'))
