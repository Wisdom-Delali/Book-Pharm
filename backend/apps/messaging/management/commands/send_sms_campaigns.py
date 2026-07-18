"""cPanel cron target — see docs/deployment.md. CLAUDE.md §8: SMS sends
must never happen inline in a request/response cycle, so the portal
composer only ever sets a campaign to SCHEDULED; this command is what
actually calls SMSOnlineGH.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.messaging.models import SmsCampaign, SmsLog
from apps.messaging.sms_client import SmsError, send_sms


class Command(BaseCommand):
    help = 'Send SmsCampaigns that are SCHEDULED and due (scheduled_for null or in the past).'

    def handle(self, *args, **options):
        if not settings.SMSONLINEGH_API_KEY:
            self.stderr.write(self.style.WARNING('SMSONLINEGH_API_KEY is not configured — skipping this run.'))
            return

        now = timezone.now()
        due = SmsCampaign.objects.filter(status=SmsCampaign.Status.SCHEDULED).filter(
            Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=now)
        )

        if not due.exists():
            self.stdout.write('No campaigns due.')
            return

        for campaign in due:
            recipients = list(campaign.recipient_queryset())
            self.stdout.write(f'Sending "{campaign.name}" to {len(recipients)} recipient(s)...')
            sent = failed = 0
            for customer in recipients:
                try:
                    ref = send_sms(to=customer.phone, message=campaign.message)
                    SmsLog.objects.create(
                        customer=customer, campaign=campaign, message=campaign.message,
                        provider_ref=ref, status=SmsLog.Status.SENT,
                    )
                    sent += 1
                except SmsError as exc:
                    SmsLog.objects.create(
                        customer=customer, campaign=campaign, message=campaign.message,
                        status=SmsLog.Status.FAILED, error=str(exc)[:255],
                    )
                    failed += 1

            campaign.status = SmsCampaign.Status.SENT
            campaign.sent_at = timezone.now()
            campaign.save(update_fields=['status', 'sent_at'])
            self.stdout.write(self.style.SUCCESS(f'"{campaign.name}": {sent} sent, {failed} failed.'))
