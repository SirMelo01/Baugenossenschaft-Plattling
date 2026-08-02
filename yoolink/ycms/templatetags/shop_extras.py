from django import template
from django.utils.html import escape, linebreaks, strip_tags
from django.utils.safestring import mark_safe

from yoolink.utils.sanitize_html import looks_like_html, sanitize_html

register = template.Library()


@register.filter
def plain_description(value):
    """Reduce rich text to condensed plain text for cards and previews."""
    # Pad tags with spaces so block boundaries don't glue words together.
    return " ".join(strip_tags((value or "").replace("<", " <")).split())


@register.filter
def rich_description(value):
    """
    Render a product description safely.

    Rich text (HTML from the CMS editor) is re-sanitized defensively before
    being marked safe. Legacy plain text descriptions keep their line breaks.
    """
    value = value or ""

    if looks_like_html(value):
        return mark_safe(sanitize_html(value))

    return mark_safe(linebreaks(escape(value)))
