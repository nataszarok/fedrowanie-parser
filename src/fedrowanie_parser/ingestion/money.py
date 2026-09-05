from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation

_MONEY_TOKEN = re.compile(r"(?<!\d)(-?\d{1,3}(?:[\s\u00a0.]\d{3})+(?:,\d{1,2})?|-?\d+(?:[.,]\d{1,2})?)(?!\d)")

def parse_money(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    s = str(value).strip()
    if not s or s in {"-", "--", "---", "-----"}:
        return None
    m = _MONEY_TOKEN.search(s.replace("\u202f", " "))
    if not m:
        return None
    token = m.group(1).replace("\u00a0", " ").replace(" ", "")
    # Polish formatting: dot normally is thousands separator when comma exists.
    if "," in token:
        token = token.replace(".", "").replace(",", ".")
    elif token.count(".") > 1:
        token = token.replace(".", "")
    try:
        return float(Decimal(token))
    except InvalidOperation:
        return None

def all_money_values(value) -> list[float]:
    if value is None:
        return []
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return [float(value)]
    s = str(value).replace("\u202f", " ")
    out=[]
    for token in _MONEY_TOKEN.findall(s):
        x=parse_money(token)
        if x is not None:
            out.append(x)
    return out
