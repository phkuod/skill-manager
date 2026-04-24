import markdown as md
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def markdownify(text):
    if not text:
        return ''
    html = md.markdown(text, extensions=['tables', 'fenced_code', 'nl2br'])
    return mark_safe(html)
