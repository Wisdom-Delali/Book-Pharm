"""ISBN normalization and internal-code generation for books without one."""

import re

import isbnlib
from django.core.exceptions import ValidationError

INTERNAL_CODE_PREFIX = 'BP-'
INTERNAL_CODE_RE = re.compile(rf'^{re.escape(INTERNAL_CODE_PREFIX)}(\d{{6}})$')


def normalize_isbn(raw):
    """Validate raw input as ISBN-10/13 and return the canonical ISBN-13
    digit string. Returns None for empty input — books legitimately have no
    ISBN. Raises ValidationError for anything non-empty that doesn't check out.
    """
    if not raw:
        return None
    cleaned = isbnlib.clean(raw)
    if not cleaned or not (isbnlib.is_isbn10(cleaned) or isbnlib.is_isbn13(cleaned)):
        raise ValidationError(f"'{raw}' is not a valid ISBN-10 or ISBN-13.")
    canonical = isbnlib.canonical(cleaned)
    if len(canonical) == 10:
        canonical = isbnlib.to_isbn13(canonical)
    return canonical


def generate_internal_code():
    """Best-effort next sequential code (BP-000001, BP-000002, ...). Not
    race-proof on its own — Book.save() retries on IntegrityError to cover
    the rare case of two concurrent inserts picking the same number.
    """
    from .models import Book

    last = (
        Book.objects.filter(internal_code__startswith=INTERNAL_CODE_PREFIX)
        .order_by('-internal_code')
        .values_list('internal_code', flat=True)
        .first()
    )
    number = 1
    if last:
        match = INTERNAL_CODE_RE.match(last)
        if match:
            number = int(match.group(1)) + 1
    return f'{INTERNAL_CODE_PREFIX}{number:06d}'
