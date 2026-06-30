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
