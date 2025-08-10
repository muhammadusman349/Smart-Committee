# yourapp/templatetags/math_filters.py
from django import template

register = template.Library()

@register.filter
def div(value, arg):
    """Divides value by arg and returns the integer result."""
    try:
        return int(value) // int(arg)
    except (ValueError, ZeroDivisionError):
        return 0