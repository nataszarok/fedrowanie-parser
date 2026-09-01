"""Semantic classification of compensation recipients.

Recipient classification belongs to enrichment rather than orchestration:
parsers recover salary records, while this module decides whether a recovered
recipient is a named physician, an anonymised physician, or a company.
"""
from __future__ import annotations

import re

from ..models import SalaryRow
from ..processing.normalization import norm_space


_COMPANY_RE = re.compile(
    r"(?ix)(?:"
    r"(?<!\w)spółk(?:a|i|ę|ą)(?!\w)|"
    r"(?<!\w)sp\s*\.?\s*z\s*\.?\s*o\s*\.?\s*o\s*\.?(?!\w)|"
    r"(?<!\w)spółka\s+z\s+ograniczoną\s+odpowiedzialnością(?!\w)|"
    r"(?<!\w)sp\s*\.?\s*k\s*\.?(?!\w)|"
    r"(?<!\w)spółka\s+komandytowa(?!\w)|"
    r"(?<!\w)s\s*\.\s*a\s*\.?(?!\w)|"
    r"(?<!\w)spółka\s+akcyjna(?!\w)|"
    r"(?<!\w)podmiot\s+leczniczy(?!\w)"
    r")"
)
_INITIALS_RE = re.compile(r"(?i)^[A-ZĄĆĘŁŃÓŚŹŻŠ](?:\.?[A-ZĄĆĘŁŃÓŚŹŻŠ]){1,2}\.?$")
_NUMBERED_INITIALS_ROW_RE = re.compile(
    r"(?i)^\s*\d+\s*\|\s*"
    r"[A-ZĄĆĘŁŃÓŚŹŻŠ](?:\.?[A-ZĄĆĘŁŃÓŚŹŻŠ]){1,2}\.?\s*\|"
)


def classify_salary_recipients(rows: list[SalaryRow], doc: str) -> list[SalaryRow]:
    """Classify recipients without adding/dropping salary rows or changing amounts."""
    lines = [norm_space(line) for line in doc.splitlines() if norm_space(line)]

    for row in rows:
        source = norm_space(row.source_name)

        if re.match(r"(?i)^z\s+zakresu\b", source):
            for i, line in enumerate(lines):
                if line == source and i > 0 and _COMPANY_RE.search(lines[i - 1]):
                    full_name = norm_space(f"{lines[i - 1]} {source}")
                    row.recipient_type = "company"
                    row.recipient_name = full_name
                    row.source_name = full_name
                    row.doctor_name = ""
                    row.doctor_initials = ""
                    source = full_name
                    break

        raw_row = norm_space(row.raw_row)
        candidate = f"{source} | {raw_row}"
        source_is_initials = bool(_INITIALS_RE.fullmatch(source.replace(" ", "")))
        raw_row_is_numbered_initials = bool(_NUMBERED_INITIALS_ROW_RE.search(raw_row))

        if (
            getattr(row, "recipient_type", "") != "company"
            and not source_is_initials
            and not raw_row_is_numbered_initials
            and _COMPANY_RE.search(candidate)
        ):
            row.recipient_type = "company"
            row.recipient_name = source
            row.doctor_name = ""
            row.doctor_initials = ""

        if getattr(row, "recipient_type", "") != "company":
            row.recipient_type = (
                "doctor" if (row.doctor_name or "").strip() else "anonymous_doctor"
            )
            row.recipient_name = (row.doctor_name or source).strip()

    return rows


__all__ = ["classify_salary_recipients"]
