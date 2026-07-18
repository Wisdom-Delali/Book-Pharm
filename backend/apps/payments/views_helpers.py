from apps.sales.models import Sale

# Paystack reports a payment "channel" per transaction; map it onto our
# Sale.PaymentMethod choices for the record. Shared by both the webhook and
# the storefront's verify-on-return view so they agree on the mapping.
PAYSTACK_CHANNEL_TO_METHOD = {
    'card': Sale.PaymentMethod.CARD,
    'mobile_money': Sale.PaymentMethod.MOMO,
    'bank': Sale.PaymentMethod.BANK_TRANSFER,
    'bank_transfer': Sale.PaymentMethod.BANK_TRANSFER,
}
