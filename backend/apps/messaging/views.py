from django.shortcuts import get_object_or_404, render

from apps.customers.models import Customer

from .tokens import read_unsubscribe_token


def unsubscribe(request, token):
    """Public, no-login self-service opt-out (ROADMAP Phase 6). Reachable
    from a link an owner-authored SMS/email can include — not auto-injected
    into every message body, since campaign wording is hers to write; see
    docs/deployment.md for how to build the link."""
    customer_id = read_unsubscribe_token(token)
    if customer_id is None:
        return render(request, 'messaging/unsubscribe.html', {'invalid': True})

    customer = get_object_or_404(Customer, pk=customer_id)
    if request.method == 'POST':
        customer.sms_opt_out = True
        customer.save(update_fields=['sms_opt_out'])
    return render(request, 'messaging/unsubscribe.html', {'customer': customer})
