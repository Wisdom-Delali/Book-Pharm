from django import template

register = template.Library()

# Thematic sidebar icons per category (falls back to a generic icon for any
# category name not listed here — the owner manages categories herself, so
# this can't assume it knows every one that will ever exist).
CATEGORY_ICONS = {
    'alchemy': 'science',
    'herbalism': 'eco',
    'medicine': 'local_pharmacy',
    'classical lit': 'history_edu',
}
DEFAULT_CATEGORY_ICON = 'category'


@register.filter
def category_icon(category_name):
    return CATEGORY_ICONS.get((category_name or '').strip().lower(), DEFAULT_CATEGORY_ICON)
