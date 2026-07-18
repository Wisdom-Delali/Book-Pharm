"""Thin Paystack client. Two calls only: initialize a transaction, verify
one. CLAUDE.md §8: verify via webhook *and* a verify-on-return call — never
trust the redirect alone — so both the webhook view and the return view in
apps/storefront end up calling verify_transaction() with the same reference.
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
        raise PaystackError(body.get('message', 'Paystack initialize failed.'))
    return body['data']  # {authorization_url, access_code, reference}


def verify_transaction(reference):
    try:
        res = requests.get(f'{PAYSTACK_BASE_URL}/transaction/verify/{reference}', headers=_headers(), timeout=15)
    except requests.RequestException as exc:
        raise PaystackError(f'Could not reach Paystack: {exc}') from exc
    body = res.json()
    if not body.get('status'):
        raise PaystackError(body.get('message', 'Paystack verify failed.'))
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
