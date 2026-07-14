from django import template
from core.utils import inr as _inr, discount_pct as _disc

register = template.Library()


@register.filter
def inr(value):
    return _inr(value)


@register.filter
def discount(mrp, selling):
    return _disc(mrp, selling)


@register.filter
def initials(name):
    name = (name or "").strip()
    return (name[0].upper() if name else "U")


@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except Exception:
        return None


@register.filter
def mul(a, b):
    try:
        return float(a) * float(b)
    except Exception:
        return 0


@register.filter
def sub(a, b):
    """a - b (used for 'add X more for free delivery')."""
    try:
        return max(float(a) - float(b), 0)
    except Exception:
        return 0


@register.filter
def div(a, b):
    try:
        return float(a) / float(b)
    except Exception:
        return 0


@register.filter
def split(value, sep=","):
    return (value or "").split(sep)


@register.filter
def get_item(d, key):
    try:
        return d[int(key)]
    except (KeyError, TypeError, ValueError):
        try:
            return d[key]
        except (KeyError, TypeError):
            return None
