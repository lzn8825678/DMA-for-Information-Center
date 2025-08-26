from django import template
register = template.Library()

@register.filter
def to(value, max_val):
    return range(int(value), int(max_val))