"""Structural parsing for salary records embedded in ordinary text/OCR lines.

This module deliberately does not know institution names or database details.  It only
recognises a source label and a monetary value, leaving person enrichment to person.py.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
from .money import parse_money

_MONEY = r"(?:-?\d{1,3}(?:[ \u00a0.]\d{3})+(?:,\d{2})?|-?\d+(?:[.,]\d{2}))"
_NUMBERED = re.compile(
    rf"^\s*(?P<no>\d{{1,4}})\s*[.)]\s*(?P<label>.+?)\s*(?:[—–~\-]|=|:)\s*"
    rf"(?P<amount>{_MONEY})\s*(?P<currency>z(?:ł|l|i|\x7d))?\s*(?P<kind>brutto|netto)?\s*[,.;]?\s*$",
    re.I,
)
_TRAILING = re.compile(
    rf"^\s*(?P<label>.+?)\s+(?P<amount>{_MONEY})\s*(?P<currency>z(?:ł|l|i|\x7d))?\s*"
    rf"(?P<kind>brutto|netto)?\s*[,.;|\]\)]*\s*$",
    re.I,
)

@dataclass(frozen=True)
class TextSalaryRecord:
    source_name: str
    amount: float
    kind: str  # gross | net | total
    numbered: bool = False


def parse_salary_text_line(line: str) -> TextSalaryRecord | None:
    """Parse one salary list/OCR line without guessing a person's identity."""
    s=re.sub(r"\s+", " ", str(line or "")).strip()
    if not s:
        return None
    m=_NUMBERED.match(s)
    numbered=bool(m)
    if not m:
        m=_TRAILING.match(s)
    if not m:
        return None
    label=m.group('label').strip(' |;,:—–-=[]')
    amount=parse_money(m.group('amount'))
    if amount is None or amount < 100 or not label:
        return None
    kind_token=(m.groupdict().get('kind') or '').casefold()
    kind='net' if kind_token=='netto' else 'gross' if kind_token=='brutto' else 'total'
    return TextSalaryRecord(label, amount, kind, numbered)
