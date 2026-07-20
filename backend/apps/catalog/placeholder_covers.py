"""Generates a simple placeholder cover (solid color + title/author) for
sample/dev books that don't have a real one. There's nothing to fetch for
fictional seed titles, and generating locally avoids both a copyright
question and a network dependency — consistent with this project's
offline-first ethos elsewhere.

placeholder_cover_url() is a second, URL-based flavor of the same idea
(owner request, 2026-07-20): a local upload (what generate_placeholder_cover()
below produces) lives on disk under MEDIA_ROOT, which isn't part of the
database and doesn't survive a deployment that doesn't also ship/persist
media files — Vercel's UAT environment, specifically (see
config/settings/vercel.py). Book.cover_image_url exists for exactly that
gap: a plain URL renders correctly regardless of deployment or filesystem
state. Both flavors share PALETTE and the same title-hash color pick, so a
given book reads as the same color whichever one is actually in play.
"""

import hashlib
import io
from pathlib import Path
from urllib.parse import quote

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 500, 750

# (background, text) pairs pulled straight from theme-storefront.css's
# secondary/primary/tertiary tokens and their "on" colors, so generated
# covers read as part of the same design language instead of generic
# gray placeholders.
PALETTE = [
    ('#af2b3e', '#ffffff'),  # secondary (burgundy)
    ('#735c00', '#ffffff'),  # primary (gold/olive)
    ('#77574d', '#ffffff'),  # tertiary (wood-brown)
    ('#5b3e35', '#f5ede4'),  # on-tertiary-container tone, used as a bg here for a 4th variant
]

# Absolute Windows paths first (this project's current dev machine), then
# common Linux/macOS locations — best-effort, not exhaustive. Falls back to
# Pillow's built-in font rather than raising if none exist, since a missing
# system font shouldn't break `seed_catalog` on an unfamiliar machine.
_TITLE_FONT_CANDIDATES = [
    'C:/Windows/Fonts/georgiab.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf',
    '/System/Library/Fonts/Supplemental/Georgia Bold.ttf',
]
_AUTHOR_FONT_CANDIDATES = [
    'C:/Windows/Fonts/georgiai.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf',
    '/System/Library/Fonts/Supplemental/Georgia Italic.ttf',
]


def _load_font(candidates, size):
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()  # older Pillow: fixed-size bitmap font, no `size` kwarg


def _wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ''
    for word in words:
        candidate = f'{current} {word}'.strip()
        if not current or draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _pick_palette(title):
    """Deterministic on title, not random — the same book always gets the
    same color whether it's asked for today or after a redeploy, and
    whether it comes out as a generated PNG or a placeholder URL."""
    index = int(hashlib.md5(title.encode('utf-8')).hexdigest(), 16) % len(PALETTE)
    return PALETTE[index]


def placeholder_cover_url(title):
    """A placehold.co URL rendering the title as text, in the same
    color/palette pick as generate_placeholder_cover() below — set on
    Book.cover_image_url, not cover_image, so nothing needs to be uploaded
    or stored on disk. See module docstring for why this exists alongside
    the PNG-generating flavor rather than replacing it."""
    bg, fg = _pick_palette(title)
    return f'https://placehold.co/{WIDTH}x{HEIGHT}/{bg.lstrip("#")}/{fg.lstrip("#")}.png?text={quote(title)}'


def generate_placeholder_cover(title, author=''):
    """Returns a django ContentFile of PNG bytes — pass straight to
    book.cover_image.save(name, generate_placeholder_cover(...))."""
    bg, fg = _pick_palette(title)

    img = Image.new('RGB', (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)

    margin = 36
    draw.rectangle([margin, margin, WIDTH - margin, HEIGHT - margin], outline=fg, width=2)

    title_font = _load_font(_TITLE_FONT_CANDIDATES, 40)
    author_font = _load_font(_AUTHOR_FONT_CANDIDATES, 26)

    text_width = WIDTH - margin * 2 - 40
    title_lines = _wrap_text(draw, title, title_font, text_width)
    author_lines = _wrap_text(draw, author, author_font, text_width) if author else []

    line_height = title_font.size + 10
    author_line_height = author_font.size + 6
    rule_gap = 24
    block_height = len(title_lines) * line_height
    if author_lines:
        block_height += rule_gap + len(author_lines) * author_line_height
    y = (HEIGHT - block_height) / 2

    for line in title_lines:
        w = draw.textlength(line, font=title_font)
        draw.text(((WIDTH - w) / 2, y), line, font=title_font, fill=fg)
        y += line_height

    if author_lines:
        y += rule_gap - author_line_height / 2
        rule_half_width = 30
        draw.line([(WIDTH / 2 - rule_half_width, y), (WIDTH / 2 + rule_half_width, y)], fill=fg, width=2)
        y += author_line_height / 2 + 8
        for line in author_lines:
            w = draw.textlength(line, font=author_font)
            draw.text(((WIDTH - w) / 2, y), line, font=author_font, fill=fg)
            y += author_line_height

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return ContentFile(buffer.getvalue())
