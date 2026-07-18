"""Ghana phone normalization. Phone is the customer's identity key
(CLAUDE.md §9) — every customer-facing entry point must funnel through this
before touching the database, or the same person ends up as two rows.
"""

import re

from django.core.exceptions import ValidationError


def normalize_phone(raw):
    """Normalize a Ghana phone number to +233XXXXXXXXX (9 digits after the
    country code). Accepts local (0XXXXXXXXX), bare country code
    (233XXXXXXXXX), or already-normalized (+233XXXXXXXXX) input, with
    optional spaces/dashes. Raises ValidationError for anything else.
    """
    if not raw:
        raise ValidationError('Phone number is required.')
    digits = re.sub(r'[\s\-()]', '', raw)

    if digits.startswith('+233'):
        national = digits[4:]
    elif digits.startswith('233'):
        national = digits[3:]
    elif digits.startswith('0'):
        national = digits[1:]
    else:
        national = digits

    if not re.fullmatch(r'\d{9}', national):
        raise ValidationError(f"'{raw}' is not a valid Ghana phone number.")
    return f'+233{national}'
