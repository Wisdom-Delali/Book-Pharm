"""ROADMAP Phase 6: "Phone normalization + dedup — merge existing
duplicates". Customer.phone is DB-unique, so two rows can only exist for the
same real person if their *stored* strings differ but normalize to the same
value — which only happens for rows written without going through
Customer.save() (e.g. a future CSV import of the owner's records from her
old POS via bulk_create, or a raw-SQL/fixture load). This is a real,
reusable operational tool for that migration, not a one-off script.
"""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.customers.models import Customer
from apps.customers.phone import normalize_phone
from apps.sales.models import Sale


class Command(BaseCommand):
    help = (
        'Find Customer rows whose phone numbers normalize to the same value and merge '
        'them into one: keeps the oldest row, reassigns Sales and loyalty history, sums '
        'loyalty_points, fills in blank fields from the duplicates, deletes the rest.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report what would merge without writing anything.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        groups = {}
        for customer in Customer.objects.all():
            try:
                key = normalize_phone(customer.phone)
            except ValidationError:
                self.stderr.write(self.style.WARNING(f'Skipping Customer #{customer.pk}: unparseable phone {customer.phone!r}'))
                continue
            groups.setdefault(key, []).append(customer)

        merged_groups = 0
        for phone, dupes in groups.items():
            if len(dupes) < 2:
                continue
            dupes.sort(key=lambda c: c.created_at)
            keeper, extras = dupes[0], dupes[1:]
            self.stdout.write(f'{phone}: merging {len(extras)} duplicate(s) into Customer #{keeper.pk} ({keeper})')
            merged_groups += 1
            if dry_run:
                continue

            with transaction.atomic():
                for dupe in extras:
                    Sale.objects.filter(customer=dupe).update(customer=keeper)
                    dupe.loyalty_transactions.update(customer=keeper)
                    keeper.loyalty_points += dupe.loyalty_points
                    keeper.full_name = keeper.full_name or dupe.full_name
                    keeper.email = keeper.email or dupe.email
                    keeper.birthday = keeper.birthday or dupe.birthday
                    keeper.sms_opt_out = keeper.sms_opt_out or dupe.sms_opt_out
                    dupe.delete()
                keeper.phone = phone
                keeper.save()

        if merged_groups == 0:
            self.stdout.write(self.style.SUCCESS('No duplicate customers found.'))
        else:
            verb = 'Would merge' if dry_run else 'Merged'
            self.stdout.write(self.style.SUCCESS(f'{verb} {merged_groups} duplicate group(s).'))
