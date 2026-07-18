"""Thin SMSOnlineGH client — one function, send one SMS. Mirrors
apps/payments/paystack.py's shape (module-level function, one exception
type, reads settings directly so nothing else touches os.environ).

CLAUDE.md §8: "sends go through a management command triggered by cron...
never send from a request/response cycle" — this module has no view calling
it directly; only apps/messaging/management/commands/ does.

Unverified against a live account: written against SMSOnlineGH's commonly
documented HTTP API shape, but SMSONLINEGH_API_KEY is still empty in .env
(client hasn't set up the account yet — same situation Paystack was in
before Phase 5, see docs/SRS.md). Re-check the endpoint path, payload keys,
and auth header against SMSOnlineGH's current docs once real credentials
exist — do not assume this wire format is correct without that check.
"""

import requests
from django.conf import settings

SMSONLINEGH_BASE_URL = 'https://api.smsonlinegh.com/v5'


class SmsError(Exception):
    pass


def send_sms(*, to, message):
    """`to` is a single +233XXXXXXXXX number. One recipient per call, not
    a bulk send — deliberately, so the caller can log a per-customer
    SmsLog row against a real per-customer result rather than guessing at
    which recipients a bulk response's partial failures refer to. Returns
    the provider's message/reference id on success; raises SmsError
    otherwise, for the caller to catch per-recipient."""
    if not settings.SMSONLINEGH_API_KEY:
        raise SmsError('SMSONLINEGH_API_KEY is not configured.')

    payload = {
        'sender': settings.SMSONLINEGH_SENDER_ID,
        'message': message,
        'destinations': [to.lstrip('+')],
        'type': 0,
    }
    headers = {
        'Authorization': f'Key {settings.SMSONLINEGH_API_KEY}',
        'Content-Type': 'application/json',
    }
    try:
        res = requests.post(f'{SMSONLINEGH_BASE_URL}/message/sms/send', json=payload, headers=headers, timeout=15)
    except requests.RequestException as exc:
        raise SmsError(f'Could not reach SMSOnlineGH: {exc}') from exc

    if res.status_code >= 400:
        raise SmsError(f'SMSOnlineGH returned {res.status_code}: {res.text[:300]}')

    body = res.json()
    return body.get('id') or body.get('message_id') or ''
