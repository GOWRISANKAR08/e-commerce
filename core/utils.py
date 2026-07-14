"""Helpers ported from src/lib/utils.ts and src/lib/constants.ts."""
import random
import re
import time


def slugify(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"(^-|-$)", "", s)


def gen_code(prefix: str) -> str:
    """Port of genCode — PREFIX-<base36 time><base36 rand>."""
    def b36(n):
        digits = "0123456789abcdefghijklmnopqrstuvwxyz"
        if n == 0:
            return "0"
        out = ""
        while n:
            n, r = divmod(n, 36)
            out = digits[r] + out
        return out
    return f"{prefix}-{b36(int(time.time() * 1000))}{b36(random.randint(0, 9999))}".upper()


def inr(n) -> str:
    """Indian-rupee formatting, no decimals — mirrors Intl en-IN currency."""
    try:
        n = round(float(n or 0))
    except (TypeError, ValueError):
        n = 0
    s = str(abs(n))
    if len(s) > 3:
        last3 = s[-3:]
        rest = s[:-3]
        rest = re.sub(r"(?<=\d)(?=(\d\d)+$)", ",", rest)
        s = rest + "," + last3
    return ("-" if n < 0 else "") + "₹" + s


def discount_pct(mrp, selling) -> int:
    if not mrp or mrp <= selling:
        return 0
    return round((mrp - selling) / mrp * 100)


# ── Position management ──────────────────────────────────────────────────────

def next_position(model, **kwargs):
    """Return max(position) + 1 for the filtered queryset."""
    from django.db.models import Max
    result = model.objects.filter(**kwargs).aggregate(m=Max("position"))["m"]
    return (result or 0) + 1


def insert_at_position(model, target_pos, **kwargs):
    """Shift all records with position >= target_pos up by 1 to make room for a new record."""
    from django.db.models import F
    model.objects.filter(position__gte=target_pos, **kwargs).update(position=F("position") + 1)


def move_to_position(model, pk, new_pos, old_pos, **kwargs):
    """Move one record to new_pos, shifting only the affected range.

    Call this AFTER saving the record with the new position so that
    surrounding records are adjusted to keep the sequence gap-free.
    """
    from django.db.models import F
    from django.db import transaction as _tx
    if new_pos == old_pos:
        return
    with _tx.atomic():
        if new_pos < old_pos:
            # Moving up: records between [new_pos, old_pos-1] shift down by 1
            model.objects.filter(
                position__gte=new_pos, position__lt=old_pos, **kwargs
            ).exclude(pk=pk).update(position=F("position") + 1)
        else:
            # Moving down: records between (old_pos, new_pos] shift up by -1
            model.objects.filter(
                position__gt=old_pos, position__lte=new_pos, **kwargs
            ).exclude(pk=pk).update(position=F("position") - 1)


def repack_positions(model, order_field="position", **kwargs):
    """Re-number positions sequentially from 1, preserving relative order.

    Use after deleting records to fill the gap cleanly.
    """
    from django.db import transaction as _tx
    with _tx.atomic():
        for i, obj in enumerate(
            model.objects.filter(**kwargs).order_by(order_field), 1
        ):
            if obj.position != i:
                model.objects.filter(pk=obj.pk).update(position=i)
