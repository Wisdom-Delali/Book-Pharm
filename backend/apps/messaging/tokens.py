"""Signed, stateless unsubscribe tokens — a customer must not be able to opt
another customer out just by guessing a phone number/id in a URL."""

from django.core import signing

SALT = 'apps.messaging.unsubscribe'


def make_unsubscribe_token(customer_id):
    return signing.dumps(customer_id, salt=SALT)


def read_unsubscribe_token(token):
    """Returns the customer id, or None if the token is invalid/tampered."""
    try:
        return signing.loads(token, salt=SALT)
    except signing.BadSignature:
        return None
