from django.db import migrations


def seed_default_program(apps, schema_editor):
    LoyaltyProgram = apps.get_model('customers', 'LoyaltyProgram')
    # Without a row here, points accrual/redemption silently does nothing
    # everywhere (LoyaltyProgram.current() returns None) rather than working
    # with sane defaults — the owner can still retune the rate in the
    # portal, but the feature shouldn't be a no-op out of the box.
    if not LoyaltyProgram.objects.exists():
        LoyaltyProgram.objects.create()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0002_loyaltyprogram_customer_sms_opt_out_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_default_program, noop),
    ]
