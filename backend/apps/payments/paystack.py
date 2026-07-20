"""Thin Paystack client. Three calls: initialize a (redirect-flow)
transaction, charge mobile money directly (prompt/OTP to the customer's
phone, no redirect), and verify — either flow's reference is checked the
same way. CLAUDE.md §8: verify via webhook *and* a verify-on-return call —
never trust the redirect alone — so both the webhook view and the return
view in apps/storefront end up calling verify_transaction() with the same
reference. The desktop POS's MoMo flow follows the same principle: webhook
is the durable confirmation, the manual "check status" button is the
verify-on-return equivalent for a POS terminal instead of a browser redirect.
"""

import hashlib
import hmac

import requests
from django.conf import settings

PAYSTACK_BASE_URL = 'https://api.paystack.co'


class PaystackError(Exception):
    pass


def _headers():
    return {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }


def _error_message(body, fallback):
    """On a rejected charge, Paystack's top-level `message` is often just a
    generic envelope string (e.g. "Charge attempted") while the actually
    useful reason sits in `data.message` (e.g. "Declined. Please use the
    test mobile money number since you are doing a test transaction.") —
    confirmed against the real API, not assumed. Prefer the specific one;
    fall back to the envelope message for errors that never got as far as
    creating a `data` object at all (bad key, malformed request)."""
    detail = (body.get('data') or {}).get('message')
    return detail or body.get('message', fallback)


def initialize_transaction(*, email, amount_ghs, reference, callback_url):
    """amount_ghs is a Decimal/GHS amount — Paystack wants the smallest unit
    (pesewas), so multiply by 100 and round to an int here, once, in the one
    place this conversion happens."""
    payload = {
        'email': email,
        'amount': int(amount_ghs * 100),
        'reference': reference,
        'callback_url': callback_url,
    }
    try:
        res = requests.post(f'{PAYSTACK_BASE_URL}/transaction/initialize', json=payload, headers=_headers(), timeout=15)
    except requests.RequestException as exc:
        raise PaystackError(f'Could not reach Paystack: {exc}') from exc
    body = res.json()
    if not body.get('status'):
        raise PaystackError(_error_message(body, 'Paystack initialize failed.'))
    return body['data']  # {authorization_url, access_code, reference}


def charge_mobile_money(*, email, amount_ghs, reference, phone, provider):
    """Ghana Mobile Money direct charge — a prompt/OTP request pushed
    straight to the customer's phone, distinct from initialize_transaction()'s
    redirect/authorization_url flow. Used by the desktop POS's MoMo payment
    button (owner request, 2026-07-20): the attendant enters the customer's
    number, this sends the prompt, and the same reference is then polled via
    verify_transaction() — no separate verify path needed for this flow.
    `provider` is Paystack's Ghana mobile money code: 'mtn', 'vod'
    (Vodafone/Telecel), or 'atl' (AirtelTigo)."""
    payload = {
        'email': email,
        'amount': int(amount_ghs * 100),
        'currency': 'GHS',
        'reference': reference,
        'mobile_money': {'phone': phone, 'provider': provider},
    }
    try:
        res = requests.post(f'{PAYSTACK_BASE_URL}/charge', json=payload, headers=_headers(), timeout=15)
    except requests.RequestException as exc:
        raise PaystackError(f'Could not reach Paystack: {exc}') from exc
    body = res.json()
    if not body.get('status'):
        raise PaystackError(_error_message(body, 'Paystack charge failed.'))
    return body['data']  # {reference, status: 'send_otp'|'pay_offline'|'success'|'failed'|..., display_text, ...}


def verify_transaction(reference):
    try:
        res = requests.get(f'{PAYSTACK_BASE_URL}/transaction/verify/{reference}', headers=_headers(), timeout=15)
    except requests.RequestException as exc:
        raise PaystackError(f'Could not reach Paystack: {exc}') from exc
    body = res.json()
    if not body.get('status'):
        raise PaystackError(_error_message(body, 'Paystack verify failed.'))
    return body['data']  # {status: 'success'|'failed'|..., amount, reference, ...}


def verify_webhook_signature(request):
    """Paystack signs webhook bodies with HMAC-SHA512 of the secret key.
    Reject anything that doesn't match — otherwise anyone who finds the
    webhook URL could fabricate a 'payment succeeded' call."""
    signature = request.headers.get('x-paystack-signature', '')
    computed = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode('utf-8'), request.body, hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(signature, computed)
